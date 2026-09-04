from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Hotel, Search, Event, Reservation

client=TestClient(app)
def test_scenario_a_complete_path():
    r=client.post('/start',data={'name':'scenario-a','age':'30'},follow_redirects=False); assert r.status_code==303
    tomorrow=date.today()+timedelta(days=1); later=tomorrow+timedelta(days=2)
    r=client.post('/search',data={'region':'Tokyo','checkin':tomorrow.isoformat(),'checkout':later.isoformat(),'guests':'2','rooms':'1','sort':'recommended'},follow_redirects=False)
    assert r.status_code==303; sid=r.headers['location'].split('/')[-1]
    page=client.get(r.headers['location']); assert page.status_code==200
    db=SessionLocal(); search=db.get(Search,sid); assert search.total_result_count>0
    hotel=db.query(Hotel).filter_by(city_name='Tokyo').first(); db.close()
    assert client.get(f'/hotel/{hotel.hotel_id}?search_id={sid}').status_code==200
    assert client.post('/event',json={'event_name':'back_to_results','page_name':'detail','search_id':sid,'hotel_id':hotel.hotel_id}).status_code==200
    r2=client.post('/search',data={'region':'Tokyo','checkin':tomorrow.isoformat(),'checkout':later.isoformat(),'guests':'2','rooms':'1','max_price':'250000','parent_search_id':sid},follow_redirects=False); sid2=r2.headers['location'].split('/')[-1]
    assert client.get(r2.headers['location']).status_code==200
    assert client.get(f'/booking/{hotel.hotel_id}?search_id={sid2}').status_code==200
    assert client.post(f'/booking/{hotel.hotel_id}?search_id={sid2}').status_code==200
    db=SessionLocal(); assert db.get(Search,sid2).parent_search_id==sid; assert db.query(Reservation).filter_by(search_id=sid2).count()==1
    names=[x.event_name for x in db.query(Event).filter_by(search_id=sid2).order_by(Event.event_time).all()]
    assert 'search_submit' in names and 'booking_complete' in names; db.close()

def test_admin_and_exports():
    assert client.get('/admin').status_code==200
    for name in ['users','hotels','searches','search_filters','events','reviews','reservations','analysis_event_log']:
        r=client.get(f'/admin/export/{name}.csv'); assert r.status_code==200; assert 'text/csv' in r.headers['content-type']

def test_anonymous_entry_and_safe_booking_cancel():
    anon=TestClient(app)
    r=anon.get('/',follow_redirects=False); assert r.status_code==303 and r.headers['location']=='/search'
    assert anon.get('/search').status_code==200
    tomorrow=date.today()+timedelta(days=1); later=tomorrow+timedelta(days=2)
    r=anon.post('/search',data={'region':'Tokyo','checkin':tomorrow.isoformat(),'checkout':later.isoformat(),'guests':'2','rooms':'1','free_cancellation':'on','pay_at_hotel':'on'},follow_redirects=False)
    sid=r.headers['location'].split('/')[-1]; db=SessionLocal(); hotel=db.query(Hotel).filter_by(city_name='Tokyo',free_cancellation=True,pay_at_hotel=True).first(); db.close()
    assert hotel is not None
    assert anon.get(f'/booking/{hotel.hotel_id}?search_id={sid}').status_code==200
    cancel=anon.get(f'/booking/{hotel.hotel_id}/cancel?search_id={sid}',follow_redirects=False)
    assert cancel.status_code==303 and f'/hotel/{hotel.hotel_id}' in cancel.headers['location']
