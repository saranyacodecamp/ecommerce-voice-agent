from mcp.server.fastmcp import FastMCP
from typing import List, Optional
import sqlite3
import os
from datetime import date, timedelta
import json
from contextlib import contextmanager
import re
import chromadb
from sentence_transformers import SentenceTransformer


DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ecommerce_data.db")
POLICIES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policies.txt")

# Initialize the database and create tables

def init_database():
    """Initialize the SQLite database with required tables"""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Create customers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                cust_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                phone_number INTEGER UNIQUE,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                seller TEXT,
                rating TEXT,
                price REAL, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Create orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cust_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER,
                order_date DATE,
                status TEXT DEFAULT 'ORDER PLACED',
                delivery_date DATE,       
                FOREIGN KEY (cust_id) REFERENCES customers (cust_id)
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            )
        ''')
        
        
        conn.commit()
        conn.close()
        print(f"Database initialized successfully at: {DATABASE_PATH}")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        print(f"Database path: {DATABASE_PATH}")
        raise

init_database()

# RAG Setup for Policies
embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("policies")

def chunk_policies(content: str) -> list:
    """Split the policy text on 2 or more newlines to create chunks"""
    chunks = re.split(r'\n{2,}', content)
    return [chunk.strip() for chunk in chunks if chunk.strip()]

def load_policies():
    """load policy text from file, chunk it and store in chromaDB"""
    if collection.count() > 0:
        print("Policies already loaded in ChromaDB.")
        return
    with open(POLICIES_PATH, 'r') as file:
        content = file.read()

    chunks = chunk_policies(content)
    collection.add(documents=chunks, embeddings=embedder.encode(chunks).tolist(), ids=[f"policy_{i}" for i in range(len(chunks))])
    print(f"Loaded {len(chunks)} policy chunks into ChromaDB.")

load_policies()


# Create MCP server
mcp = FastMCP("Ecommerce Server")

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # hands conn to the tool
        yield conn        
    finally:
        conn.close()      


@mcp.tool()
def customer_exists(phone_number: int) -> dict:
    """Check if customer exists and return the customer id"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cust_id FROM customers WHERE phone_number = ?", (phone_number,))
        customer = cursor.fetchone()
    if customer:
        return {"exists": True, "cust_id": customer["cust_id"]}
    else:
        return {"exists": False, "message": f"No customer found with phone {phone_number}"}


#Order Management Tools

@mcp.tool()
def check_order_status(cust_id: str, order_id: int) -> dict:
    """Check the order status of the customer"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            # Get the order from the orders table based on order and customer id
            cursor.execute("SELECT product_id,quantity,order_date,status,delivery_date FROM orders WHERE id = ? AND cust_id = ?", (order_id, cust_id))
            order = cursor.fetchone()                  
            if not order:
                return {"error": f"No order found with ID {order_id} for customer {cust_id}"}
            return {
                "order_id": order_id,
                "product_id": order["product_id"],
                "quantity": order["quantity"],
                "order_date": order["order_date"],
                "status": order["status"],
                "delivery_date": order["delivery_date"],
            }
    except Exception as e:
        return {"error": f"Error querying orders: {str(e)}"}
    

@mcp.tool()
def cancel_order(cust_id: str, order_id: int) -> dict:
    """Cancel the order of the customer based on order id and customer id"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            # Get the order from the orders table based on order and customer id
            cursor.execute("SELECT status FROM orders WHERE id = ? AND cust_id = ?", (order_id, cust_id))
            order = cursor.fetchone()
        
            if not order:
                return {"error": f"Order {order_id} not found for customer {cust_id}"}
        
            if order["status"] in ("DELIVERED", "Cancelled"):
                return {"success": False, "message": f"Order {order_id} cannot be cancelled. Current status: {order['status']}"}

            status = "Cancelled"
            
            #Update status field in the orders table
            cursor.execute("UPDATE orders SET status = ? WHERE id = ? AND cust_id = ?", (status, order_id, cust_id))
        
            conn.commit()
            return {"success": True, "message": f"Order {order_id} has been cancelled successfully."}
                    
    except Exception as e:
        return {"error": f"Error cancelling order: {str(e)}"}

@mcp.tool()
def list_all_orders(cust_id: str) -> dict:
    """List all orders takes customer id as input and list orders of the customer """
    try:
        with get_db() as conn:
            cursor = conn.cursor()          
            cursor.execute("SELECT id, product_id, quantity, order_date, status, delivery_date FROM orders WHERE cust_id = ?", (cust_id,))
            orders = cursor.fetchall()
           
            if not orders:
                return {"error": f"No orders found for customer {cust_id}."}

        order_details = [{
                "order_id": order[0],
                "product_id": order[1],
                "quantity": order[2],
                "order_date": order[3],
                "status": order[4],
                "delivery_date": order[5],
            } for order in orders ]                                                                                                                                                                                                                                                                            

        return order_details                                                                                                                              
    except Exception as e:
        return {"error": f"Error listing orders: {str(e)}"}
    

@mcp.tool()
def update_customer_details(customer_id: str, name: str = None, email: str = None, address: str = None) -> dict:
    """Update customer details"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            # Get customer details
            cursor.execute("SELECT cust_id, name, email, address FROM customers WHERE cust_id = ?", (customer_id,))
            
            customer = cursor.fetchone()
            if not customer:
                return {"error": f"Customer {customer_id} not found."}
        
            current_name = customer["name"]
            current_email = customer["email"]
            current_address = customer["address"]

            # Update customer details if provided
            if name is not None:
                current_name = name
            if email is not None:
                current_email = email
            if address is not None:
                current_address = address
            cursor.execute('''
                UPDATE customers SET name = ?, email = ?, address = ? WHERE cust_id = ?
                ''', (current_name, current_email, current_address, customer_id))

            conn.commit()
            return {"success": True, "message": f"Customer details updated successfully for ID {customer_id}."}
       
    except Exception as e:
        return {"success": False, "message": f"Error getting customer details: {str(e)}"}

@mcp.tool()
def get_product_details(product_id: str) -> dict:
    """Get product details based on product id"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, description, seller, rating, price FROM products WHERE product_id = ?", (product_id,))
            product = cursor.fetchone()
        
            if not product:
                return {"error": f"Product {product_id} not found."}
        
            return {
                "name": product["name"],
                "description": product["description"],
                "seller": product["seller"],
                "rating": product["rating"],
                "price": product["price"],
            }
    except Exception as e:
        return {"error": f"Error getting product details: {str(e)}"}
@mcp.tool()
def search_products(query: str) -> dict:
    """Search products based on query string"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            # Search for products where name or description matches the query
            cursor.execute("SELECT product_id, name, description, seller, rating, price FROM products WHERE name LIKE ? OR description LIKE ?", (f"%{query}%", f"%{query}%"))
            products = cursor.fetchall()
        
            if not products:
                return {"error": f"No products found matching query '{query}'."}
        
            product_list = [{
                "product_id": product["product_id"],
                "name": product["name"],
                "description": product["description"],
                "seller": product["seller"],
                "rating": product["rating"],
                "price": product["price"],
            } for product in products]
        
            return {"products": product_list}
    except Exception as e:
        return {"error": f"Error searching products: {str(e)}"}
    
@mcp.tool()
def place_order(cust_id: str, product_id: str, quantity: int) -> dict:
    """Place a new order for the customer """
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Check if product exists
            cursor.execute("SELECT product_id FROM products WHERE product_id = ?", (product_id,))
            if not cursor.fetchone():
                return {"error": f"Product {product_id} not found."}
        
            order_date = date.today()
            delivery_date = date.today() + timedelta(days=5)  
            status = "ORDER PLACED"
        
            cursor.execute('''
                INSERT INTO orders (cust_id, product_id, quantity, order_date, status, delivery_date) 
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (cust_id, product_id, quantity, order_date, status, delivery_date))
        
            conn.commit()
            return {"success": True, "message": f"Order placed successfully for customer {cust_id}."}
    except Exception as e:
        return {"error": f"Error placing order: {str(e)}"}
    
@mcp.tool()
def search_policy(query: str) -> dict:
    """Search policy documents for questions about returns, cancellations,
    delivery, refunds, exchange, warranty, payments, and other store policies"""
    try:
        query_embedding = embedder.encode([query]).tolist()
        results = collection.query(query_embeddings=query_embedding, n_results=2)
        if not results['documents'][0]:
            return {"found": False, "message": "No policy found for this query"}
        return {"found": True, "policy": results['documents'][0]}
    except Exception as e:
        return {"error": f"Error searching policies: {str(e)}"}

# Initialize with sample data
def init_sample_data():
    """Initialize database with sample data for demo purposes"""
    with get_db() as conn:
        cursor = conn.cursor()
    
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM customers")
        if cursor.fetchone()[0] > 0:
            return  # Data already exists
    
        # Sample customers
        sample_customers = [
            ("C001", "John Smith", "john.smith@gmail.com", 9900454094, "123 Main St, Bangalore, Karnataka"),
            ("C002", "Sarah Johnson", "sarah.johnson@gmail.com", 9900454095, "456 Oak Ave, Chennai, Tamil Nadu"),
            ("C003", "Mike Wilson", "mike.wilson@gmail.com", 9900454096, "789 Pine Rd, Madurai, Tamil Nadu"),
            ("C004", "Emily Brown", "emily.brown@gmail.com", 9900454097, "321 Elm St, Mysore, Karnataka"),
            ("C005", "David Lee", "david.lee@gmail.com", 9900454098, "654 Maple Dr, Mumbai, Maharashtra"),
        ]
    
        for cust_data in sample_customers:
            cursor.execute('''
                INSERT INTO customers (cust_id, name, email, phone_number, address)
                VALUES (?, ?, ?, ?, ?)
                    ''', cust_data)

        sample_products = [
            ("P001", "Laptop", "Latest model laptop with advanced features", "HP", 4.5, 50000.00),
            ("P002", "Smartphone", "Latest model smartphone with advanced features", "Samsung", 4.0, 699.99),
            ("P003", "Tablet", "Versatile tablet for work and entertainment", "Apple", 4.2, 399.99),
            ("P004", "Headphones", "Noise-cancelling headphones for immersive audio", "Sony", 4.7, 199.99),
            ("P005", "Smartwatch", "Feature-rich smartwatch for fitness and connectivity", "Garmin", 4.3, 299.99),
        ]
    
        for prod_data in sample_products:
            cursor.execute('''INSERT INTO products (product_id, name, description, seller, rating, price)
                    VALUES (?, ?, ?, ?, ?, ?)''', prod_data)

        sample_orders = [
            ("C001", "P001", 1, "2026-06-01", "ORDER PLACED", "2026-06-05"),
            ("C002", "P002", 2, "2026-06-02", "ORDER PLACED", "2026-06-06"),
            ("C003", "P003", 1, "2026-06-03", "ORDER PLACED", "2026-06-07"),
            ("C004", "P004", 3, "2026-06-04", "ORDER PLACED", "2026-06-08"),
            ("C005", "P005", 1, "2026-06-05", "ORDER PLACED", "2026-06-09"),
        ]

        
        for order_data in sample_orders:
            cursor.execute('''INSERT INTO orders (cust_id,product_id,quantity,order_date,status,delivery_date) 
                       values(?, ?, ?, ?, ?, ?)''', order_data)

   
        conn.commit()
    
# Initialize sample data
init_sample_data()




# To start the server:
if __name__ == "__main__":
    mcp.run()