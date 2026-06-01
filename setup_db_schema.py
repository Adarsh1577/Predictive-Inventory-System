"""
Database schema setup script.
Creates the products, inventory, and stock_transactions tables needed by the system.
"""
import mysql.connector
import pandas as pd

def setup_database_schema():
    print("🔧 Setting up database schema...")
    
    # Connect to MySQL
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Aps@JC-857079N",
        database="inventory_system"
    )
    cursor = conn.cursor()
    
    try:
        # 1. Create products table
        print("📋 Creating 'products' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INT PRIMARY KEY,
            product_name VARCHAR(255) NOT NULL,
            reorder_level INT DEFAULT 10
        );
        """)
        
        # 2. Create inventory table
        print("📊 Creating 'inventory' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            product_id INT PRIMARY KEY,
            current_stock INT DEFAULT 0,
            reorder_level INT DEFAULT 10,
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
        """)
        
        # 3. Create stock_transactions table
        print("📝 Creating 'stock_transactions' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_transactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            transaction_date DATE NOT NULL,
            product_id INT NOT NULL,
            quantity_changed INT NOT NULL,
            transaction_type VARCHAR(50),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
        """)

        # 4. Create procurement_alerts table for automated procurement tracking
        print("🛎️ Creating 'procurement_alerts' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS procurement_alerts (
            alert_id INT AUTO_INCREMENT PRIMARY KEY,
            product_id INT NOT NULL,
            product_name VARCHAR(255) NOT NULL,
            alert_generated DATE NOT NULL,
            depletion_date DATE NOT NULL,
            days_to_depletion INT NOT NULL,
            predicted_7_day_total INT NOT NULL,
            recommended_order_qty INT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_product_depletion (product_id, depletion_date),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
        """)
        
        conn.commit()
        print("✅ Schema tables created successfully!")
        
        # 4. Populate products table if empty
        cursor.execute("SELECT COUNT(*) FROM products;")
        if cursor.fetchone()[0] == 0:
            print("📥 Populating 'products' table...")
            products_data = [
                (101, "Wireless Headphones", 10),
                (102, "Mechanical Keyboard", 8),
                (103, "Ergonomic Gaming Mouse", 12)
            ]
            cursor.executemany(
                "INSERT INTO products (product_id, product_name, reorder_level) VALUES (%s, %s, %s)",
                products_data
            )
            conn.commit()
            print("✅ Products table populated!")
        
        # 5. Populate stock_transactions from historical_sales if needed
        cursor.execute("SELECT COUNT(*) FROM stock_transactions;")
        if cursor.fetchone()[0] == 0:
            print("📥 Populating 'stock_transactions' from historical_sales...")
            df = pd.read_csv("historical_sales.csv")
            for _, row in df.iterrows():
                cursor.execute("""
                INSERT INTO stock_transactions (transaction_date, product_id, quantity_changed, transaction_type)
                VALUES (%s, %s, %s, %s)
                """, (row['Date'], row['Product_ID'], -row['Quantity_Sold'], 'SALES'))
            conn.commit()
            print(f"✅ Loaded {len(df)} transactions into stock_transactions!")
        
        # 6. Initialize inventory levels (set current_stock to a reasonable starting value)
        cursor.execute("SELECT COUNT(*) FROM inventory;")
        if cursor.fetchone()[0] == 0:
            print("📥 Initializing 'inventory' table...")
            inventory_data = [
                (101, 100, 10),
                (102, 80, 8),
                (103, 120, 12)
            ]
            cursor.executemany(
                "INSERT INTO inventory (product_id, current_stock, reorder_level) VALUES (%s, %s, %s)",
                inventory_data
            )
            conn.commit()
            print("✅ Inventory table initialized!")
        
    except Exception as e:
        print(f"❌ Error during schema setup: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
        print("🔌 Database connection closed.")

if __name__ == "__main__":
    setup_database_schema()
