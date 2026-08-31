import csv, io, json, uuid
from datetime import date, datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession
from .database import Base, engine, get_db
from .models import User, Session, Hotel, Search, SearchFilter, Event, Review, Reservation

ROOT=Path(__file__).resolve().parents[1]; app=FastAPI(title="StayTrace"); Base.metadata.create_all(engine)
def migrate_columns():
    additions={
        "hotels":{"free_cancellation":"BOOLEAN NOT NULL DEFAULT 0","pay_at_hotel":"BOOLEAN NOT NULL DEFAULT 0","breakfast_included":"BOOLEAN NOT NULL DEFAULT 0","pet_friendly":"BOOLEAN NOT NULL DEFAULT 0","family_room":"BOOLEAN NOT NULL DEFAULT 0","swimming_pool":"BOOLEAN NOT NULL DEFAULT 0","spa":"BOOLEAN NOT NULL DEFAULT 0","chain_name":"VARCHAR(50)"},
        "search_filters":{"free_cancellation_required":"BOOLEAN NOT NULL DEFAULT 0","pay_at_hotel_required":"BOOLEAN NOT NULL DEFAULT 0","pet_friendly_required":"BOOLEAN NOT NULL DEFAULT 0","family_room_required":"BOOLEAN NOT NULL DEFAULT 0","swimming_pool_required":"BOOLEAN NOT NULL DEFAULT 0","spa_required":"BOOLEAN NOT NULL DEFAULT 0","chain_name":"VARCHAR(50)"}}
    with engine.begin() as conn:
        for table,columns in additions.items():
            existing={row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            for name,definition in columns.items():
                if name not in existing: conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
migrate_columns()
app.mount("/static",StaticFiles(directory=ROOT/"app/static"),name="static"); templates=Jinja2Templates(directory=ROOT/"app/templates")
def uid(prefix): return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"
def ctx(request):
    return request.cookies.get("user_id"),request.cookies.get("session_id")
def log(db,user,session,name,page,search=None,hotel=None,props=None,filter_id=None):
    if not user or not session: return
    db.add(Event(event_id=uid("EVT"),action_id=uid("ACT"),user_id=user,session_id=session,event_name=name,page_name=page,search_id=search,hotel_id=hotel,search_filter_id=filter_id,event_properties_json=json.dumps(props or {},ensure_ascii=False)))
def selected_hotels(db,s,f):
    q=db.query(Hotel).filter(func.lower(Hotel.city_name)==s.search_region.lower())
    if f.accommodation_type: q=q.filter(Hotel.accommodation_type==f.accommodation_type)
    if f.accommodation_grade: q=q.filter(Hotel.grade>=f.accommodation_grade)
    if f.min_rating: q=q.filter(Hotel.hotel_rating>=f.min_rating)
    if f.min_price: q=q.filter(Hotel.price_per_night>=f.min_price)
    if f.max_price: q=q.filter(Hotel.price_per_night<=f.max_price)
    if f.max_station_distance_m: q=q.filter(Hotel.station_distance_m<=f.max_station_distance_m)
    for key,active in [("breakfast",f.breakfast_required),("parking",f.parking_required),("public_bath",f.public_bath_required),("free_wifi",f.free_wifi_required)]:
        if active: q=q.filter(Hotel.amenities_json.contains(key))
    for column,active in [(Hotel.free_cancellation,f.free_cancellation_required),(Hotel.pay_at_hotel,f.pay_at_hotel_required),(Hotel.pet_friendly,f.pet_friendly_required),(Hotel.family_room,f.family_room_required),(Hotel.swimming_pool,f.swimming_pool_required),(Hotel.spa,f.spa_required)]:
        if active: q=q.filter(column.is_(True))
    if f.breakfast_required: q=q.filter(Hotel.breakfast_included.is_(True))
    if f.chain_name: q=q.filter(Hotel.chain_name==f.chain_name)
    if s.sort_condition=="price_low": q=q.order_by(Hotel.price_per_night)
    elif s.sort_condition=="rating_high": q=q.order_by(Hotel.hotel_rating.desc())
    else: q=q.order_by(Hotel.hotel_rating.desc(),Hotel.review_count.desc())
    return q.all()

@app.get("/",response_class=HTMLResponse)
def home(request:Request,db:DBSession=Depends(get_db)):
    u,s=ctx(request)
    if u and s and db.get(User,u) and db.get(Session,s): return RedirectResponse("/search",303)
    user=User(user_id=uid("USR"),user_name=f"익명여행자-{uuid.uuid4().hex[:4].upper()}"); db.add(user); db.flush()
    ses=Session(session_id=uid("SES"),user_id=user.user_id); db.add(ses); db.flush(); log(db,user.user_id,ses.session_id,"session_start","landing",props={"anonymous":True}); db.commit()
    r=RedirectResponse("/search",303); r.set_cookie("user_id",user.user_id,httponly=True,samesite="lax",max_age=60*60*24*30); r.set_cookie("session_id",ses.session_id,httponly=True,samesite="lax",max_age=60*60*24*30); return r
@app.post("/start")
def start(name:str=Form(...),age:int|None=Form(None),phone:str|None=Form(None),db:DBSession=Depends(get_db)):
    user=User(user_id=uid("USR"),user_name=name,age=age,phone_number=phone or None); ses=Session(session_id=uid("SES"),user_id=user.user_id)
    db.add(user); db.flush(); db.add(ses); db.flush(); log(db,user.user_id,ses.session_id,"session_start","start"); db.commit()
    r=RedirectResponse("/search",303); r.set_cookie("user_id",user.user_id,httponly=True,samesite="lax"); r.set_cookie("session_id",ses.session_id,httponly=True,samesite="lax"); return r
@app.get("/search",response_class=HTMLResponse)
def search_page(request:Request,db:DBSession=Depends(get_db)):
    u,s=ctx(request)
    if not u or not s or not db.get(User,u) or not db.get(Session,s):return RedirectResponse("/",303)
    log(db,u,s,"search_start","search"); log(db,u,s,"page_view","search"); db.commit()
    return templates.TemplateResponse("search.html",{"request":request,"today":date.today().isoformat()})
@app.post("/search")
async def submit_search(request:Request,db:DBSession=Depends(get_db)):
    u,ses=ctx(request)
    if not u or not ses: return RedirectResponse("/",303)
    form=await request.form(); parent=form.get("parent_search_id") or None; sid=uid("SRC"); fid=uid("FLT")
    s=Search(search_id=sid,user_id=u,session_id=ses,query_text=str(form.get("region","Tokyo")),search_region=str(form.get("region","Tokyo")),checkin_date=date.fromisoformat(str(form["checkin"])),checkout_date=date.fromisoformat(str(form["checkout"])),guest_count=int(form.get("guests",2)),room_count=int(form.get("rooms",1)),sort_condition=str(form.get("sort","recommended")),parent_search_id=parent)
    f=SearchFilter(search_filter_id=fid,search_id=sid,accommodation_type=form.get("type") or None,accommodation_grade=int(form["grade"]) if form.get("grade") else None,min_rating=float(form["min_rating"]) if form.get("min_rating") else None,min_price=int(form["min_price"]) if form.get("min_price") else None,max_price=int(form["max_price"]) if form.get("max_price") else None,max_station_distance_m=int(form["distance"]) if form.get("distance") else None,breakfast_required="breakfast" in form,parking_required="parking" in form,public_bath_required="public_bath" in form,free_wifi_required="free_wifi" in form,free_cancellation_required="free_cancellation" in form,pay_at_hotel_required="pay_at_hotel" in form,pet_friendly_required="pet_friendly" in form,family_room_required="family_room" in form,swimming_pool_required="swimming_pool" in form,spa_required="spa" in form,chain_name=form.get("chain") or None,amenities_json="[]",region=str(form.get("region")))
    db.add(s); db.flush(); db.add(f); db.flush(); hotels=selected_hotels(db,s,f); s.total_result_count=len(hotels)
    log(db,u,ses,"search_submit","search",sid,props={"parent_search_id":parent,"conditions":dict(form)},filter_id=fid)
    log(db,u,ses,"search_result_view" if hotels else "search_no_result","results",sid,props={"result_count":len(hotels)},filter_id=fid); db.commit()
    return RedirectResponse(f"/results/{sid}",303)
@app.get("/results/{sid}",response_class=HTMLResponse)
def results(sid:str,request:Request,db:DBSession=Depends(get_db)):
    u,ses=ctx(request); s=db.get(Search,sid)
    if not s or s.user_id!=u: raise HTTPException(404)
    hotels=selected_hotels(db,s,s.filter)
    for rank,h in enumerate(hotels,1):
        log(db,u,ses,"hotel_impression","results",sid,h.hotel_id,{"rank":rank,"result_count":len(hotels),"sort":s.sort_condition},s.filter.search_filter_id)
    try: db.commit()
    except IntegrityError: db.rollback()
    wishes={x.hotel_id for x in db.query(Event).filter(Event.user_id==u,Event.event_name.in_(["wishlist_add","wishlist_remove"])).order_by(Event.event_time).all() if x.event_name=="wishlist_add"}
    return templates.TemplateResponse("results.html",{"request":request,"hotels":hotels,"search":s,"filter":s.filter,"wishes":wishes})
@app.get("/hotel/{hid}",response_class=HTMLResponse)
def detail(hid:str,request:Request,search_id:str,db:DBSession=Depends(get_db)):
    u,ses=ctx(request); h=db.get(Hotel,hid); s=db.get(Search,search_id)
    if not h or not s: raise HTTPException(404)
    log(db,u,ses,"hotel_click","results",search_id,hid); log(db,u,ses,"hotel_detail_view","detail",search_id,hid); log(db,u,ses,"page_view","detail",search_id,hid); db.commit()
    reviews=db.query(Review).filter_by(hotel_id=hid).order_by(Review.review_created_at.desc()).all()
    log(db,u,ses,"review_view","detail",search_id,hid,{"review_count":len(reviews)}); db.commit()
    return templates.TemplateResponse("detail.html",{"request":request,"hotel":h,"search":s,"reviews":reviews})
@app.post("/event")
async def track(request:Request,db:DBSession=Depends(get_db)):
    u,s=ctx(request); p=await request.json(); log(db,u,s,p["event_name"],p.get("page_name","unknown"),p.get("search_id"),p.get("hotel_id"),p.get("properties")); db.commit(); return {"ok":True}
@app.get("/end")
def end_session(request:Request,db:DBSession=Depends(get_db)):
    u,s=ctx(request)
    if u and s:
        log(db,u,s,"exit","site"); log(db,u,s,"session_end","site"); session=db.get(Session,s)
        if session: session.ended_at=datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    r=RedirectResponse("/",303); r.delete_cookie("user_id"); r.delete_cookie("session_id"); return r
@app.get("/booking/{hid}",response_class=HTMLResponse)
def booking(hid:str,search_id:str,request:Request,db:DBSession=Depends(get_db)):
    u,ses=ctx(request); h=db.get(Hotel,hid); s=db.get(Search,search_id); log(db,u,ses,"booking_start","booking",search_id,hid); db.commit()
    nights=max(1,(s.checkout_date-s.checkin_date).days); return templates.TemplateResponse("booking.html",{"request":request,"hotel":h,"search":s,"total":nights*s.room_count*h.price_per_night})
@app.get("/booking/{hid}/cancel")
def cancel_booking(hid:str,search_id:str,request:Request,db:DBSession=Depends(get_db)):
    u,ses=ctx(request); search=db.get(Search,search_id); hotel=db.get(Hotel,hid)
    if u and ses and search and hotel:
        log(db,u,ses,"booking_cancel","booking",search_id,hid,{"return_to":"hotel_detail"}); db.commit()
        return RedirectResponse(f"/hotel/{hid}?search_id={search_id}",303)
    return RedirectResponse("/",303)
@app.post("/booking/{hid}",response_class=HTMLResponse)
def complete(hid:str,search_id:str,request:Request,db:DBSession=Depends(get_db)):
    u,ses=ctx(request); h=db.get(Hotel,hid); s=db.get(Search,search_id); total=max(1,(s.checkout_date-s.checkin_date).days)*s.room_count*h.price_per_night
    r=Reservation(reservation_id=uid("RSV"),user_id=u,hotel_id=hid,search_id=search_id,total_price=total,checkin_date=s.checkin_date,checkout_date=s.checkout_date,guest_count=s.guest_count,room_count=s.room_count)
    db.add(r); db.flush(); log(db,u,ses,"booking_complete","booking",search_id,hid,{"reservation_id":r.reservation_id,"total_price":total}); db.commit(); return templates.TemplateResponse("complete.html",{"request":request,"reservation":r,"hotel":h})
@app.post("/review/{hid}")
def review(hid:str,request:Request,search_id:str=Form(...),rating:float=Form(...),text:str=Form(...),db:DBSession=Depends(get_db)):
    u,s=ctx(request); db.add(Review(review_id=uid("REV"),hotel_id=hid,user_id=u,rating=rating,review_text=text)); log(db,u,s,"review_submit","detail",search_id,hid,{"rating":rating}); db.commit(); return RedirectResponse(f"/hotel/{hid}?search_id={search_id}",303)

TABLES={"users":User,"hotels":Hotel,"searches":Search,"search_filters":SearchFilter,"events":Event,"reviews":Review,"reservations":Reservation}
@app.get("/admin",response_class=HTMLResponse)
def admin(request:Request,session_id:str|None=None,db:DBSession=Depends(get_db)):
    counts={k:db.query(v).count() for k,v in TABLES.items()}; names=["hotel_click","wishlist_add","booking_start","booking_complete"]
    metrics={n:db.query(Event).filter_by(event_name=n).count() for n in names}; metrics["sessions"]=db.query(Session).count(); metrics["re_searches"]=db.query(Search).filter(Search.parent_search_id.is_not(None)).count()
    events=db.query(Event).filter(Event.session_id==session_id) if session_id else db.query(Event); events=events.order_by(Event.event_time.desc()).limit(200).all()
    sessions=db.query(Session).order_by(Session.started_at.desc()).all(); return templates.TemplateResponse("admin.html",{"request":request,"counts":counts,"metrics":metrics,"events":events,"sessions":sessions,"selected":session_id})
@app.get("/admin/export/{name}.csv")
def export(name:str,db:DBSession=Depends(get_db)):
    if name=="analysis_event_log":
        rows=db.query(Event,Search,SearchFilter,Hotel).outerjoin(Search,Event.search_id==Search.search_id).outerjoin(SearchFilter,Event.search_filter_id==SearchFilter.search_filter_id).outerjoin(Hotel,Event.hotel_id==Hotel.hotel_id).all()
        headers=["user_id","session_id","search_id","event_id","event_time","event_name","hotel_id","search_region","query_text","sort_condition","accommodation_type","min_rating","min_price","max_price","hotel_name","hotel_price","hotel_rating","hotel_grade"]
        data=[[e.user_id,e.session_id,e.search_id,e.event_id,e.event_time,e.event_name,e.hotel_id,s.search_region if s else None,s.query_text if s else None,s.sort_condition if s else None,f.accommodation_type if f else None,f.min_rating if f else None,f.min_price if f else None,f.max_price if f else None,h.hotel_name if h else None,h.price_per_night if h else None,h.hotel_rating if h else None,h.grade if h else None] for e,s,f,h in rows]
    elif name in TABLES:
        model=TABLES[name]; headers=[c.name for c in model.__table__.columns]; data=[[getattr(x,c) for c in headers] for x in db.query(model).all()]
    else: raise HTTPException(404)
    out=io.StringIO(); w=csv.writer(out); w.writerow(headers); w.writerows(data); return StreamingResponse(iter([out.getvalue().encode("utf-8-sig")]),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="{name}.csv"'})
