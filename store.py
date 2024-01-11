from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
import sqlite3
import threading
import cgi
import uuid
import os
from PIL import Image
import mysql.connector

class DatabaseManager:
    def __init__(self, host, user, password, database):
        self.connection_params = {
            'host': host,
            'user': user,
            'password': password,
            'database': database
        }

    def create_tables(self):
        conn = mysql.connector.connect(**self.connection_params)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                is_deleted BOOLEAN DEFAULT 0
                
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                category_id INT,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT,
                price FLOAT,
                quantity INT,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT,
                image_path TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        conn.close()

    def execute_query(self, query, values=None, fetch=True):
        with mysql.connector.connect(**self.connection_params) as conn:
            cursor = conn.cursor()
            try:
                if values:
                    cursor.execute(query, values)
                else:
                    cursor.execute(query)

                if 'INSERT' in query.upper():
                    # Return the last inserted ID for INSERT queries
                    last_row_id = cursor.lastrowid
                    
                elif 'UPDATE' in query.upper() or 'DELETE' in query.upper():
                    # Return the number of affected rows for UPDATE and DELETE queries
                    last_row_id = cursor.rowcount
                else:
                    # Fetch or iterate through the results if the query produces any
                    last_row_id = None
                    if fetch:
                        last_row_id = cursor.fetchall()  # or fetchone(), or iterate over cursor

                conn.commit()
                return last_row_id

            finally:
                cursor.close()


class CategoryHandler(BaseHTTPRequestHandler):
    db_manager = DatabaseManager(
        host='127.0.0.1',
        user='root',
        password='root',
        database='shoplast2'
    )
    db_manager.create_tables()
    
    def _send_response(self, status_code, response_body):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(response_body.encode('utf-8'))
        
    

    def do_GET(self):
        if self.path == '/categories':
            try:
                categories = self.db_manager.execute_query('SELECT * FROM categories')
                response_data = [{'id': cat[0], 'name': cat[1]} for cat in categories]
                response_body = json.dumps(response_data)
                self._send_response(200, response_body)
            except Exception as e:
                print(f"Error retrieving categories: {e}")
                self._send_response(500, 'Internal Server Error')
        else:
            self._send_response(404, 'Not Found')

    def do_POST(self):
        if self.path == '/categories':
            content_length = int(self.headers['Content-Length'])
            category_data = json.loads(self.rfile.read(content_length).decode('utf-8'))

            # Assuming category_data is a dictionary with a 'name' key
            query = 'INSERT INTO categories (name) VALUES (%s)'
            values = (category_data.get('name'),)
            
            # Execute the query and get the assigned ID
            new_category_id = self.db_manager.execute_query(query, values)
            
            # Directly access the 'new_category_id' without fetching additional results
            response_body = json.dumps({'id': new_category_id, 'name': category_data.get('name')})
            self._send_response(201, response_body)
        else:
            self._send_response(404, 'Not Found')



    def do_PUT(self):
        if self.path.startswith('/categories/'):
            category_id = int(self.path.split('/')[2])
            content_length = int(self.headers['Content-Length'])
            category_data = json.loads(self.rfile.read(content_length).decode('utf-8'))

            # Assuming category_data is a dictionary with a 'name' key
            query = 'UPDATE categories SET name = %s WHERE id = %s'
            values = (category_data.get('name'), category_id)

            try:
                # Execute the query and get the number of affected rows
                affected_rows = self.db_manager.execute_query(query, values)
                if affected_rows > 0:
                    response_body = json.dumps({'id': category_id, 'name': category_data.get('name')})
                    self._send_response(200, response_body)
                else:
                    self._send_response(404, 'Category not found')
            except Exception as e:
                print(f"Error updating category: {e}")
                self._send_response(500, 'Internal Server Error')
        else:
            self._send_response(404, 'Not Found')
            
    def do_DELETE(self):
        if self.path.startswith('/categories/'):
            try:
                category_id = int(self.path.split('/')[2])

                # Check if the category exists before attempting to delete
                category = self.db_manager.execute_query('SELECT * FROM categories WHERE id = %s', (category_id,))
                if not category:
                    self._send_response(404, 'Category not found')
                    return

                # Delete the category
                self.db_manager.execute_query('DELETE FROM categories WHERE id = %s', (category_id,))

                self._send_response(200, 'Category deleted successfully')
            except ValueError:
                self._send_response(400, 'Invalid category ID format')
            except Exception as e:
                print(f"Error deleting category: {e}")
                self._send_response(500, 'Internal Server Error')
        else:
            self._send_response(404, 'Not Found')


            
    def do_DELETE(self):
        if self.path.startswith('/categories_soft/'):
            try:
                category_id = int(self.path.split('/')[2])

                # Check if the category exists before attempting to delete
                category = self.db_manager.execute_query('SELECT * FROM categories WHERE id = %s', (category_id,))
                if not category:
                    self._send_response(404, 'Category not found')
                    return

                # Soft delete the category by updating is_deleted to 1
                self.db_manager.execute_query('UPDATE categories SET is_deleted = 1 WHERE id = %s', (category_id,))

                self._send_response(200, 'Category soft deleted successfully')
            except ValueError:
                self._send_response(400, 'Invalid category ID format')
            except Exception as e:
                print(f"Error deleting category: {e}")
                self._send_response(500, 'Internal Server Error')
        else:
            self._send_response(404, 'Not Found')


    
    



class ProductHandler(BaseHTTPRequestHandler):
    db_manager = DatabaseManager(
        host='127.0.0.1',
        user='root',
        password='root',
        database='shoplast2'
    )
    db_manager.create_tables()

    def _send_response(self, status_code, response_body):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(response_body.encode('utf-8'))

    
    
    def do_GET(self):
        if self.path == '/products':
            products = self._get_all_products_with_prices_and_images()
            response_data = [
                {
                    'id': product['id'],
                    'name': product['name'],
                    'category_id': product['category_id'],
                    'prices': product['prices'],
                    'images': product['images']
                }
                for product in products
            ]
            response_body = json.dumps(response_data)
            self._send_response(200, response_body)
        else:
            self._send_response(404, 'Not Found')

    def _get_all_products_with_prices_and_images(self):
        # Retrieve all products with their associated prices and images
        query = '''
            SELECT
                products.id,
                products.name,
                products.category_id,
                prices.price,
                prices.quantity,
                images.id AS image_id,
                images.image_path
            FROM products
            LEFT JOIN prices ON products.id = prices.product_id
            LEFT JOIN images ON products.id = images.product_id
        '''
        result = self.db_manager.execute_query(query, fetch=True)

        products = {}
        for row in result:
            (
                product_id,
                product_name,
                category_id,
                price,
                quantity,
                image_id,
                image_path
            ) = row

            if product_id not in products:
                products[product_id] = {
                    'id': product_id,
                    'name': product_name,
                    'category_id': category_id,
                    'prices': [],
                    'images': []
                }

            if price is not None:
                products[product_id]['prices'].append({'price': price, 'quantity': quantity})

            if image_id is not None:
                image_info = {
                    'id': image_id,
                    'image': image_path.replace('\\', '/'),
                    'thumbnail': self._get_thumbnail_path(image_path).replace('\\', '/'),
                    'thumbnail400': self._get_thumbnail_path400(image_path).replace('\\', '/'),
                    'thumbnail1200': self._get_thumbnail_path1200(image_path).replace('\\', '/'),
                }
                products[product_id]['images'].append(image_info)

        return list(products.values())

    def _get_product_with_prices(self, product_id):
        # Retrieve all products with their associated prices
        query = '''
            SELECT products.id, products.name, products.category_id, prices.price, prices.quantity
            FROM products
            LEFT JOIN prices ON products.id = prices.product_id
            WHERE products.id = %s
        '''
        result = self.db_manager.execute_query(query, (product_id,), fetch=True)

        product_data = None
        prices = []

        for row in result:
            product_id, product_name, category_id, price, quantity = row

            if product_data is None:
                product_data = {'id': product_id, 'name': product_name, 'category_id': category_id, 'prices': []}

            if price is not None:
                prices.append({'price': price, 'quantity': quantity})

        if product_data:
            product_data['prices'] = prices

        return [product_data] if product_data else []

            
    def do_POST(self):
        if self.path == '/products':
            content_length = int(self.headers['Content-Length'])
            product_data = json.loads(self.rfile.read(content_length).decode('utf-8'))

            # Extract product details
            name = product_data.get('name')
            category_id = product_data.get('category_id')
            prices_data = product_data.get('prices', [])

            # Check if name, category_ids, and prices are provided
            if not name or not category_id or not prices_data:
                self._send_response(400, 'Name, category_id, and prices are required')
                return

            # Check if all categories with the provided IDs exist in the database
            if not self._categories_exist(category_id):
                self._send_response(400, 'Invalid category_id provided')
                return

            # Check if prices have the required "price" field
            if not all('price' in price_data for price_data in prices_data):
                self._send_response(400, 'Each price must have a "price" field')
                return

            # Insert new product into the database
            category_id_str = ','.join(map(str, category_id))
            query = 'INSERT INTO products (name, category_id) VALUES (%s, %s)'
            values = (name, category_id_str)
            

            # Retrieve the newly inserted product from the database
            
            new_product_id = self.db_manager.execute_query(query, values, fetch=False)

            # Insert prices into the database
            self._insert_prices_for_product(new_product_id, prices_data)

            # Retrieve the product with prices from the database
            new_product = self._get_product_with_prices(new_product_id)

            self._send_response(201, json.dumps(new_product))
        else:
            self._send_response(404, 'Not Found')

    def _categories_exist(self, category_id):
        # Check if all categories with the provided IDs exist in the database
        for category_i in category_id:
            query = 'SELECT * FROM categories WHERE id = %s'
            values = (category_i,)
            result = self.db_manager.execute_query(query, values, fetch=True)

            if not result:
                return False  # No category found with the given ID

        return True

    def _insert_prices_for_product(self, product_id, prices_data):
        # Insert prices into the database for a given product
        query = 'INSERT INTO prices (product_id, price, quantity) VALUES (%s, %s, %s)'
        
        for price_data in prices_data:
            price = price_data.get('price')
            quantity = price_data.get('quantity', 100)  # Default quantity to 100 if not provided
            values = (product_id, price, quantity)
            print(values)  # Debugging statement
            self.db_manager.execute_query(query, values)
            
    
    def do_PUT(self):
        if self.path.startswith('/products/'):
            product_id = self.path.split('/')[2]
            content_length = int(self.headers['Content-Length'])
            product_data = json.loads(self.rfile.read(content_length).decode('utf-8'))

            # Extract updated product details
            name = product_data.get('name')
            category_id = product_data.get('category_id')
            prices_data = product_data.get('prices', [])

            # Check if name, category_ids, and prices are provided
            if not name or not category_id or not prices_data:
                self._send_response(400, 'Name, category_id, and prices are required')
                return

            # Check if all categories with the provided IDs exist in the database
            if not self._categories_exist(category_id):
                self._send_response(400, 'Invalid category_id provided')
                return

            # Check if prices have the required "price" field
            if not all('price' in price_data for price_data in prices_data):
                self._send_response(400, 'Each price must have a "price" field')
                return

            # Update the product in the database
            category_id_str = ','.join(map(str, category_id))
            query = 'UPDATE products SET name=%s, category_id=%s WHERE id=%s'
            values = (name, category_id_str, product_id)

            # Check if the product exists before updating
            if not self._product_exists(product_id):
                self._send_response(404, 'Product not found')
                return

            self.db_manager.execute_query(query, values, fetch=False)

            # Update prices in the database
            self._update_prices_for_product(product_id, prices_data)

            # Retrieve the updated product with prices from the database
            updated_product = self._get_product_with_prices(product_id)

            self._send_response(200, json.dumps(updated_product))
        else:
            self._send_response(404, 'Not Found')
            
    def _product_exists(self, product_id):
        query = 'SELECT id FROM products WHERE id = %s'
        values = (product_id,)
        result = self.db_manager.execute_query(query, values, fetch=True)

        return bool(result)

    def _update_prices_for_product(self, product_id, prices_data):
        # Update prices for a given product
        delete_query = 'DELETE FROM prices WHERE product_id = %s'
        insert_query = 'INSERT INTO prices (product_id, price, quantity) VALUES (%s, %s, %s)'

        # Delete existing prices for the product
        self.db_manager.execute_query(delete_query, (product_id,))

        # Insert new prices for the product
        for price_data in prices_data:
            price = price_data.get('price')
            quantity = price_data.get('quantity', 100)  # Default quantity to 100 if not provided
            values = (product_id, price, quantity)
            self.db_manager.execute_query(insert_query, values)
            
    

    def do_DELETE(self):
        if self.path.startswith('/products/'):
            product_id = int(self.path.split('/')[2])

            # Delete product by ID
            query = 'DELETE FROM products WHERE id = %s'
            values = (product_id,)

            try:
                affected_rows = self.db_manager.execute_query(query, values)
                if affected_rows > 0:
                    self._send_response(204, '')  # 204 No Content for successful deletion
                else:
                    self._send_response(404, 'Product not found')
            except Exception as e:
                print(f"Error deleting product: {e}")
                self._send_response(500, 'Internal Server Error')
        else:
            self._send_response(404, 'Not Found')

        
    def _get_thumbnail_path(self, original_image_path):
        # Assuming the thumbnails are saved in the 'thumbnails' subdirectory
        thumbnail_directory = os.path.join(os.path.dirname(original_image_path), 'thumbnails')
        
        # Construct the thumbnail filename based on the original image's filename
        thumbnail_filename = 'thumbnail_' + os.path.basename(original_image_path)

        # Construct the full path to the thumbnail
        thumbnail_path = os.path.join(thumbnail_directory, thumbnail_filename)

        return thumbnail_path
    def _get_thumbnail_path400(self, original_image_path):
        # Assuming the thumbnails are saved in the 'thumbnails' subdirectory
        image_directory = 'images'
        thumbnail_directory = os.path.join(image_directory, 'thumbnail400')
        
        # Construct the thumbnail filename based on the original image's filename
        thumbnail_filename = 'thumbnail400_' + os.path.basename(original_image_path)

        # Construct the full path to the thumbnail
        thumbnail_path = os.path.join(thumbnail_directory, thumbnail_filename)

        return thumbnail_path
    def _get_thumbnail_path1200(self, original_image_path):
        # Assuming the thumbnails are saved in the 'thumbnails' subdirectory
        image_directory = 'images'
        thumbnail_directory = os.path.join(image_directory, 'thumbnail1200')
        
        # Construct the thumbnail filename based on the original image's filename
        thumbnail_filename = 'thumbnail1200_' + os.path.basename(original_image_path)

        # Construct the full path to the thumbnail
        thumbnail_path = os.path.join(thumbnail_directory, thumbnail_filename)

        return thumbnail_path


class ImageHandler(BaseHTTPRequestHandler):
    db_manager = DatabaseManager(
        host='127.0.0.1',
        user='root',
        password='root',
        database='shoplast2'
    )
    db_manager.create_tables()
    def _send_response(self, status_code, response_body):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(response_body.encode('utf-8'))
        
    def do_GET(self):
        if self.path == '/images':
            images = self.db_manager.execute_query('SELECT * FROM images')
            response_data = []

            for img in images:
                image_path = img[2].replace('\\', '/')
                thumbnail_path = self._get_thumbnail_path(img[2]).replace('\\', '/')
                thumbnail_path400 = self._get_thumbnail_path400(img[2]).replace('\\', '/')
                thumbnail_path1200 = self._get_thumbnail_path1200(img[2]).replace('\\', '/')
                image_info = {
                    'id': img[0],
                    'product_id': img[1],
                    'image': image_path,
                    'thumbnail': thumbnail_path,
                    'thumbnail400':thumbnail_path400,
                    'thumbnail1200':thumbnail_path1200
                }
                response_data.append(image_info)

            response_body = json.dumps(response_data)
            self._send_response(200, response_body)
        else:
            self._send_response(404, 'Not Found')
        
    def do_POST(self):
        if self.path == '/images':
            content_type, _ = cgi.parse_header(self.headers['Content-Type'])

            # Check if the request is sending 'multipart/form-data'
            if content_type == 'multipart/form-data':
                form_data = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST',
                             'CONTENT_TYPE': self.headers['Content-Type']}
                )

                # Extract image and product_id from the form data
                image_file = form_data['image'].file
                product_id = form_data.getvalue('product_id')

                # Save the image to a file
                image_path = self._save_image_and_thumbnail(image_file)

                # Insert image information into the database
                query = 'INSERT INTO images (product_id, image_path) VALUES (%s, %s)'
                values = (product_id, image_path)
                self.db_manager.execute_query(query, values)

                self._send_response(201, 'Image uploaded successfully')
            else:
                self._send_response(400, 'Invalid Content-Type. Expected multipart/form-data')
        else:
            self._send_response(404, 'Not Found')
            
    def do_PUT(self):
        if self.path.startswith('/images/'):
            image_id = int(self.path.split('/')[2])

            content_type, _ = cgi.parse_header(self.headers['Content-Type'])

            # Check if the request is sending 'multipart/form-data'
            if content_type == 'multipart/form-data':
                form_data = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'PUT',
                            'CONTENT_TYPE': self.headers['Content-Type']}
                )

                # Extract image and product_id from the form data
                image_file = form_data['image'].file
                product_id = form_data.getvalue('product_id')

                # Save the updated image to a file
                image_path = self._save_image_and_thumbnail(image_file)

                # Update image information in the database
                query = 'UPDATE images SET product_id = %s, image_path = %s WHERE id = %s'
                values = (product_id, image_path, image_id)

                try:
                    affected_rows = self.db_manager.execute_query(query, values)
                    if affected_rows > 0:
                        self._send_response(200, 'Image updated successfully')
                    else:
                        self._send_response(404, 'Image not found')
                except Exception as e:
                    print(f"Error updating image: {e}")
                    self._send_response(500, 'Internal Server Error')
            else:
                self._send_response(400, 'Invalid Content-Type. Expected multipart/form-data')
        else:
            self._send_response(404, 'Not Found')

    def do_DELETE(self):
        if self.path.startswith('/images/'):
            image_id = int(self.path.split('/')[2])

            # Delete image by ID
            query = 'DELETE FROM images WHERE id = %s'
            values = (image_id,)

            try:
                affected_rows = self.db_manager.execute_query(query, values)
                if affected_rows > 0:
                    self._send_response(204, '')  # 204 No Content for successful deletion
                else:
                    self._send_response(404, 'Image not found')
            except Exception as e:
                print(f"Error deleting image: {e}")
                self._send_response(500, 'Internal Server Error')
        else:
            self._send_response(404, 'Not Found')


# Add a helper method to check if the image ID exists in the database
    def _image_exists(self, image_id):
        query = 'SELECT id FROM images WHERE id = ?'
        values = (image_id,)
        result = self.db_manager.execute_query(query, values).fetchone()
        return result is not None

    def _save_image_and_thumbnail(self, image_file):
        # Specify the directory where you want to save the images
        image_directory = 'images'

        # Specify the subdirectory "thumbnails" inside the "images" directory
        thumbnail_directory = os.path.join(image_directory, 'thumbnails')
        thumbnail400_directory = os.path.join(image_directory, 'thumbnail400')
        thumbnail1200_directory = os.path.join(image_directory, 'thumbnail1200')

        # Create the directories if they don't exist
        os.makedirs(image_directory, exist_ok=True)
        os.makedirs(thumbnail_directory, exist_ok=True)
        os.makedirs(thumbnail400_directory, exist_ok=True)
        os.makedirs(thumbnail1200_directory, exist_ok=True)

        # Generate unique filenames for the image and thumbnail
        image_filename = f'image_{uuid.uuid4().hex}.png'
        thumbnail_filename = f'thumbnail_{uuid.uuid4().hex}.png'
        thumbnail400_filename = f'thumbnail400_{uuid.uuid4().hex}.png'
        thumbnail1200_filename = f'thumbnail1200_{uuid.uuid4().hex}.png'

        # Construct the full paths to save the image and thumbnail
        image_path = os.path.join(image_directory, image_filename)
        thumbnail_path = os.path.join(thumbnail_directory, thumbnail_filename)
        thumbnail400_path = os.path.join(thumbnail400_directory, thumbnail400_filename)
        thumbnail1200_path = os.path.join(thumbnail1200_directory, thumbnail1200_filename)

        # Save the image to the specified path
        with open(image_path, 'wb') as f:
            f.write(image_file.read())

        # Create the thumbnail and save it inside the "thumbnails" directory
        self._create_thumbnail(image_path, thumbnail_path)
        self._create_thumbnail400(image_path, thumbnail400_path)
        self._create_thumbnail1200(image_path, thumbnail1200_path)

        return image_path

    def _create_thumbnail(self, original_image_path, thumbnail_path):
        # Open the original image
        original_image = Image.open(original_image_path)

        # Create a thumbnail with a maximum size of 100x100 pixels
        thumbnail_size = (100, 100)
        thumbnail_image = original_image.copy()
        thumbnail_image.thumbnail(thumbnail_size)

        # Save the thumbnail to the specified path
        thumbnail_image.save(thumbnail_path)
        
    def _create_thumbnail400(self, original_image_path, thumbnail_path):
        # Open the original image
        original_image = Image.open(original_image_path)

        # Create a thumbnail with a maximum size of 100x100 pixels
        thumbnail_size = (400, 400)
        thumbnail_image = original_image.copy()
        thumbnail_image.thumbnail(thumbnail_size)

        # Save the thumbnail to the specified path
        thumbnail_image.save(thumbnail_path)
        
    def _create_thumbnail1200(self, original_image_path, thumbnail_path):
        # Open the original image
        original_image = Image.open(original_image_path)

        # Create a thumbnail with a maximum size of 100x100 pixels
        thumbnail_size = (1200, 1200)
        thumbnail_image = original_image.copy()
        thumbnail_image.thumbnail(thumbnail_size)

        # Save the thumbnail to the specified path
        thumbnail_image.save(thumbnail_path)
        
    def _get_thumbnail_path(self, original_image_path):
        # Assuming the thumbnails are saved in the 'thumbnails' subdirectory
        image_directory = 'images'
        thumbnail_directory = os.path.join(image_directory, 'thumbnails')
        
        # Construct the thumbnail filename based on the original image's filename
        thumbnail_filename = 'thumbnail_' + os.path.basename(original_image_path)

        # Construct the full path to the thumbnail
        thumbnail_path = os.path.join(thumbnail_directory, thumbnail_filename)

        return thumbnail_path
    def _get_thumbnail_path400(self, original_image_path):
        # Assuming the thumbnails are saved in the 'thumbnails' subdirectory
        image_directory = 'images'
        thumbnail_directory = os.path.join(image_directory, 'thumbnail400')
        
        # Construct the thumbnail filename based on the original image's filename
        thumbnail_filename = 'thumbnail400_' + os.path.basename(original_image_path)

        # Construct the full path to the thumbnail
        thumbnail_path = os.path.join(thumbnail_directory, thumbnail_filename)

        return thumbnail_path
    def _get_thumbnail_path1200(self, original_image_path):
        # Assuming the thumbnails are saved in the 'thumbnails' subdirectory
        image_directory = 'images'
        thumbnail_directory = os.path.join(image_directory, 'thumbnail1200')
        
        # Construct the thumbnail filename based on the original image's filename
        thumbnail_filename = 'thumbnail1200_' + os.path.basename(original_image_path)

        # Construct the full path to the thumbnail
        thumbnail_path = os.path.join(thumbnail_directory, thumbnail_filename)

        return thumbnail_path
                

if __name__ == '__main__':
    host = '127.0.0.1'
    category_port = 8080
    product_port = 8081
    image_port = 8082

    # Create instances of HTTPServer
    category_server = HTTPServer((host, category_port), CategoryHandler)
    product_server = HTTPServer((host, product_port), ProductHandler)
    image_server = HTTPServer((host, image_port), ImageHandler)
    # Create threads for each server
    category_thread = threading.Thread(target=category_server.serve_forever)
    product_thread = threading.Thread(target=product_server.serve_forever)
    image_thread = threading.Thread(target=image_server.serve_forever)
    # Start both threads
    category_thread.start()
    product_thread.start()
    image_thread.start()
    
    print(f'Starting category server on http://{host}:{category_port}')
    print(f'Starting product server on http://{host}:{product_port}')
    print(f'Starting image server on http://{host}:{image_port}')
    try:
        # Join both threads to the main thread
        category_thread.join()
        product_thread.join()
        image_thread.join()
    except KeyboardInterrupt:
        category_server.shutdown()
        product_server.shutdown()
        image_server.shutdown()
        print('Servers stopped')