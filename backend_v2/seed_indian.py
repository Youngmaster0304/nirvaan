import json, os, hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base
from app.models_indian import (
    Zone, Division, Corridor, IndianTrain, Block, Department, Defect,
    CrewDuty, User, Session, EmergencyPush
)

DB_URL = settings.DATABASE_URL
if DB_URL.startswith("postgresql"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


def hash_pw(p):
    return hashlib.sha256(p.encode()).hexdigest()


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if db.query(Zone).count() > 0:
            print("Data already seeded.")
            return

        zones_data = [
            ("NR", "Northern Railway", "New Delhi"),
            ("NCR", "North Central Railway", "Prayagraj"),
            ("NER", "North Eastern Railway", "Gorakhpur"),
            ("NWR", "North Western Railway", "Jaipur"),
            ("CR", "Central Railway", "Mumbai"),
            ("SCR", "South Central Railway", "Secunderabad"),
            ("SR", "Southern Railway", "Chennai"),
            ("SWR", "South Western Railway", "Bangalore"),
            ("ECR", "East Central Railway", "Hajipur"),
            ("ER", "Eastern Railway", "Kolkata"),
            ("SER", "South Eastern Railway", "Kolkata"),
            ("WR", "Western Railway", "Mumbai"),
            ("WCR", "West Central Railway", "Jabalpur"),
            ("NFR", "Northeast Frontier Railway", "Guwahati"),
            ("SECR", "South East Central Railway", "Bilaspur"),
        ]
        for code, name, hq in zones_data:
            db.add(Zone(zone_code=code, zone_name=name, headquarters=hq))
        db.flush()

        divs_data = [
            ("DLI", "Delhi", 1), ("UMB", "Ambala", 1), ("FZR", "Firozpur", 1),
            ("PRYJ", "Prayagraj", 2), ("AGC", "Agra", 2),
            ("GKP", "Gorakhpur", 3), ("LKO", "Lucknow", 3),
            ("JP", "Jaipur", 4), ("BKN", "Bikaner", 4),
            ("CSMT", "Mumbai CSMT", 5), ("PUNE", "Pune", 5),
            ("SC", "Secunderabad", 6), ("HYB", "Hyderabad", 6),
            ("MS", "Chennai", 7),             ("TVC", "Trivandrum", 7),
            ("SBC", "Bangalore", 8), ("MYS", "Mysore", 8),
            ("HJP", "Hajipur", 9), ("DNR", "Danapur", 9),
            ("HWH", "Howrah", 10), ("SDAH", "Sealdah", 10),
            ("KGP", "Kharagpur", 11), ("CBL", "Chakradharpur", 11),
            ("BCT", "Mumbai Central", 12), ("ADI", "Ahmedabad", 12),
            ("JHS", "Jabalpur", 13), ("BPL", "Bhopal", 13),
            ("GHY", "Guwahati", 14), ("LMG", "Lumding", 14),
            ("BSP", "Bilaspur", 15), ("R", "Raipur", 15),
        ]
        for code, name, zid in divs_data:
            db.add(Division(div_code=code, div_name=name, zone_id=zid))
        db.flush()

        corridors_data = [
            ("NDLS-LKO", "New Delhi - Lucknow", 1, 13, "NDLS", "LKO", 512, "double", 130),
            ("NDLS-UMB", "New Delhi - Ambala", 1, 1, "NDLS", "UMB", 200, "double", 130),
            ("NDLS-AGC", "New Delhi - Agra", 1, 15, "NDLS", "AGC", 180, "double", 130),
            ("LKO-PRYJ", "Lucknow - Prayagraj", 3, 11, "LKO", "PRYJ", 183, "double", 110),
            ("PRYJ-MGS", "Prayagraj - Mughalsarai", 2, 11, "PRYJ", "MGS", 165, "double", 110),
            ("MGS-GAYA", "Mughalsarai - Gaya", 2, 9, "MGS", "GAYA", 130, "single", 100),
            ("GAYA-HJP", "Gaya - Hajipur", 2, 9, "GAYA", "HJP", 90, "single", 100),
            ("NDLS-BCT", "New Delhi - Mumbai", 1, 12, "NDLS", "BCT", 1384, "double", 130),
            ("CSMT-PUNE", "Mumbai - Pune", 5, 15, "CSMT", "PUNE", 120, "double", 110),
            ("SC-HYB", "Secunderabad - Hyderabad", 6, 16, "SC", "HYB", 10, "double", 110),
            ("HWH-SDAH", "Howrah - Sealdah", 10, 17, "HWH", "SDAH", 18, "double", 110),
            ("HWH-KGP", "Howrah - Kharagpur", 10, 17, "HWH", "KGP", 130, "double", 110),
            ("BCT-ADI", "Mumbai - Ahmedabad", 12, 19, "BCT", "ADI", 493, "double", 130),
            ("JHS-BPL", "Jabalpur - Bhopal", 13, 21, "JHS", "BPL", 340, "double", 110),
            ("GHY-LMG", "Guwahati - Lumding", 14, 22, "GHY", "LMG", 175, "single", 100),
            ("BSP-R", "Bilaspur - Raipur", 15, 23, "BSP", "R", 180, "double", 110),
        ]
        for cid, name, zid, did, frm, to, dist, track, speed in corridors_data:
            db.add(Corridor(corridor_id=cid, route_name=name, zone_id=zid, division_id=did, from_station=frm, to_station=to, distance_km=dist, track_type=track, max_speed_kmph=speed))
        db.flush()

        depts = [
            ("ENG", "Engineering", "#3B82F6"),
            ("TRD", "Traction Distribution", "#10B981"),
            ("SIG", "Signal & Telecom", "#F59E0B"),
            ("MCH", "Mechanical", "#EF4444"),
        ]
        for code, name, color in depts:
            db.add(Department(code=code, name=name, color=color))
        db.flush()

        db.commit()
        print("Seed data inserted successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
