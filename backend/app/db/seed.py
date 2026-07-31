from app.db.session import SessionLocal
from app.models.models import Category, Commodity

def seed_data():
    db = SessionLocal()

    categories_data = {
        "Vegetables": {
            "unit": "kg",
            "items": ["Onion", "Potato", "Tomato", "Garlic", "Ginger",
                      "Cucumber", "Spinach", "Carrot", "Cabbage",
                      "Cauliflower", "Green Chili", "Capsicum"]
        },
        "Fruits": {
            "unit": "kg",
            "items": ["Apple", "Banana", "Mango", "Orange", "Guava",
                      "Grapes", "Watermelon", "Papaya", "Pomegranate",
                      "Peach", "Plum", "Melon"]
        },
        "Dairy Products": {
            "unit": None,  # mixed units, set per item below
            "items": [("Eggs", "dozen"), ("Milk", "liter"), ("Yoghurt", "kg")]
        },
        "Poultry & Meat": {
            "unit": "kg",
            "items": ["Chicken (Farm Gate Rate)", "Chicken (Processed Rate)",
                      "Beef Meat", "Mutton"]
        },
    }

    for cat_name, data in categories_data.items():
        category = db.query(Category).filter_by(name=cat_name).first()
        if not category:
            category = Category(name=cat_name)
            db.add(category)
            db.commit()
            db.refresh(category)

        for item in data["items"]:
            if isinstance(item, tuple):
                item_name, unit = item
            else:
                item_name, unit = item, data["unit"]

            existing = db.query(Commodity).filter_by(
                category_id=category.id, name=item_name
            ).first()
            if not existing:
                db.add(Commodity(category_id=category.id, name=item_name, unit=unit))

    db.commit()
    db.close()
    print("Seed data inserted successfully.")


if __name__ == "__main__":
    seed_data()