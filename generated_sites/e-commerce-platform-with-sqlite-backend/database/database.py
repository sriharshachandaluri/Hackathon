import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "ecommerce.db")

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'customer',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        category TEXT NOT NULL,
        image_url TEXT,
        stock INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create cart_items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cart_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        quantity INTEGER NOT NULL DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, product_id)
    );
    """)

    # Create orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        total_amount REAL NOT NULL,
        shipping_address TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create order_items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
        quantity INTEGER NOT NULL,
        price_at_purchase REAL NOT NULL
    );
    """)

    # Seed products if empty
    cursor.execute("SELECT COUNT(*) as count FROM products;")
    count = cursor.fetchone()["count"]
    if count == 0:
        seed_products = [
            ("Classic Cotton Hoodie", "Soft, comfortable cotton hoodie with a drawstring and front pocket.", 45.00, "Apparel", "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=400&q=80", 50),
            ("Slim Fit Denim Jeans", "Classic slim fit denim jeans made with durable and flexible cotton fabric.", 59.99, "Apparel", "https://images.unsplash.com/photo-1542272604-787c3835535d?auto=format&fit=crop&w=400&q=80", 40),
            ("Wireless Noise-Canceling Headphones", "High fidelity wireless over-ear headphones featuring active noise cancellation.", 199.99, "Electronics", "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=400&q=80", 25),
            ("Smart Fitness Watch", "Advanced fitness tracker and smartwatch with heart rate monitoring and GPS tracking.", 129.50, "Electronics", "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=400&q=80", 30),
            ("Leather Bi-fold Wallet", "Handcrafted genuine leather wallet with RFID blocking technology.", 34.99, "Accessories", "https://images.unsplash.com/photo-1627123424574-724758594e93?auto=format&fit=crop&w=400&q=80", 60),
            ("Aviator Sunglasses", "Classic metal frame sunglasses with UV400 polarized protective lenses.", 25.00, "Accessories", "https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=400&q=80", 80),
            ("SuperComfort Running Shoes", "Lightweight, breathable running shoes designed for ultimate speed and stability.", 89.99, "Footwear", "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=400&q=80", 35),
            ("Casual Canvas Sneakers", "Simple, low-profile lifestyle sneaker perfect for casual daily wear.", 49.95, "Footwear", "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?auto=format&fit=crop&w=400&q=80", 45),
            ("Ergonomic Office Chair", "High-back mesh desk chair with adjustable lumbar support and armrests.", 149.99, "Furniture", "https://images.unsplash.com/photo-1505797149-43b0069ec26b?auto=format&fit=crop&w=400&q=80", 15),
            ("Minimalist Wooden Coffee Table", "Sleek coffee table featuring solid wood construction and open storage shelves.", 110.00, "Furniture", "https://images.unsplash.com/photo-1533090161767-e6ffed986c88?auto=format&fit=crop&w=400&q=80", 10),
            ("Premium Organic Coffee Beans", "Medium roast, whole bean organic coffee with notes of dark chocolate and citrus.", 14.99, "Groceries", "https://images.unsplash.com/photo-1447933601403-0c6688de566e?auto=format&fit=crop&w=400&q=80", 100),
            ("Roasted Almonds Pack", "Gently roasted, lightly salted California almonds. High in protein and fiber.", 9.99, "Groceries", "https://images.unsplash.com/photo-1508061253366-f7da158b6d96?auto=format&fit=crop&w=400&q=80", 120),
        ]
        cursor.executemany("""
        INSERT INTO products (name, description, price, category, image_url, stock)
        VALUES (?, ?, ?, ?, ?, ?);
        """, seed_products)
        conn.commit()
    
    conn.close()

if __name__ == "__main__":
    init_db()
