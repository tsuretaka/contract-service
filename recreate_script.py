import services
from models import SessionLocal, Contract
import sys
db = SessionLocal()
c = db.query(Contract).first()
if c:
    print(c.id, c.status)
else:
    print("none")
