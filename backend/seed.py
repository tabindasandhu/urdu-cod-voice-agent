from app import db

db.init_db()
db.create_order("Ayesha Khan", "0300-1111111", "Lawn 3-piece suit (Firozi)", 4500,
                "Lahore", "House 12, Block C, Johar Town")
db.create_order("Fatima Ali", "0301-2222222", "Ready-to-wear kurta (M) x2", 7200,
                "Karachi", "Flat 5, Block 13, Gulshan-e-Iqbal")
db.create_order("Sana Riaz", "0302-3333333", "Embroidered formal suit", 15500,
                "Multan", "Street 4, Shah Rukn-e-Alam Colony")
for o in db.list_orders():
    print(o["id"], o["customer_name"], o["amount"], o["status"])