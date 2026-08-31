import json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import Base, engine, SessionLocal
from app.models import Hotel

CITIES={"Tokyo":(35.6762,139.6503),"Osaka":(34.6937,135.5023),"Kyoto":(35.0116,135.7681),"Fukuoka":(33.5904,130.4017),"Sapporo":(43.0618,141.3545)}
AMENITIES=["free_wifi","breakfast","public_bath","parking","gym","laundry","restaurant"]
TYPES=["Hotel","Ryokan","Hostel","Apartment","Resort","Guesthouse"]
CHAINS=[None,"Sakura Stay","Nippon Grand","Urban Nest","Hoshi Resorts"]
def seed(count=180):
    Base.metadata.create_all(engine); db=SessionLocal()
    if db.query(Hotel).count() >= count:
        for i,h in enumerate(db.query(Hotel).order_by(Hotel.hotel_id)):
            h.free_cancellation=i%3!=0; h.pay_at_hotel=i%4!=0; h.breakfast_included=i%2==0
            h.pet_friendly=i%7==0; h.family_room=i%3==0; h.swimming_pool=i%5==0; h.spa=i%6==0; h.chain_name=CHAINS[i%len(CHAINS)]
        db.commit(); db.close(); print(f"Updated {count} hotels"); return
    random.seed(20260826); db.query(Hotel).delete()
    for i in range(count):
        city=list(CITIES)[i%5]; lat,lon=CITIES[city]; amenities=random.sample(AMENITIES,random.randint(2,7))
        db.add(Hotel(hotel_id=f"H{i+1:04d}",hotel_name=f"{city} {['Garden','Central','Harbor','Sky','Sakura','Grand'][i%6]} {i+1}",city_name=city,region_name=f"{city} Central",grade=random.randint(2,5),latitude=lat+random.uniform(-.08,.08),longitude=lon+random.uniform(-.08,.08),hotel_address=f"{i+1}-2 {city}, Japan",hotel_rating=round(random.uniform(6.5,9.7),1),accommodation_type=random.choice(TYPES),price_per_night=random.randrange(45000,310000,5000),review_count=random.randint(15,3200),amenities_json=json.dumps(amenities),nearest_station=f"{city} Station {i%9+1}",station_distance_m=random.randrange(80,1600,20),thumbnail_url=f"https://picsum.photos/seed/hotel{i+1}/640/400",description=f"A comfortable stay in the heart of {city}, with thoughtful service and convenient transport.",free_cancellation=i%3!=0,pay_at_hotel=i%4!=0,breakfast_included=i%2==0,pet_friendly=i%7==0,family_room=i%3==0,swimming_pool=i%5==0,spa=i%6==0,chain_name=CHAINS[i%len(CHAINS)]))
    db.commit(); db.close(); print(f"Seeded {count} hotels")
if __name__ == "__main__": seed()
