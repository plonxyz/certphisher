from flask import *
from flask_pymongo import PyMongo
from werkzeug.utils import secure_filename
from bson import ObjectId
from datetime import datetime
import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

app = Flask(__name__)

# MongoDB configuration - use environment variable or default to Docker service name
mongo_host = os.environ.get('MONGODB_HOST', 'localhost')
mongo_port = os.environ.get('MONGODB_PORT', '27017')
mongo_db = os.environ.get('MONGODB_DB', 'certphisher')
app.config["MONGO_URI"] = f"mongodb://{mongo_host}:{mongo_port}/{mongo_db}"

app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

mongo = PyMongo(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def start():
    sites = mongo.db.sites.find({"checked_vt": "true"}).limit(25).sort("_id", -1)
    sites_count = mongo.db.sites.count_documents({"checked_vt": "true"})
    sites_critical_count = mongo.db.sites.count_documents({"checked_vt": "true","certphisher_score": { "$gt": 140}})
    sites_high_count = mongo.db.sites.count_documents({"checked_vt": "true","certphisher_score": { "$gte" : 90, "$lt": 140}})
    sites_medium_count = mongo.db.sites.count_documents({"checked_vt": "true","certphisher_score": { "$gte" : 80, "$lt": 90}})
    return render_template("index.html",
        sites=sites, sites_count = sites_count, sites_critical_count = sites_critical_count, sites_high_count = sites_high_count, sites_medium_count = sites_medium_count)

@app.route('/alltime')
def alltime():
        sites = mongo.db.sites.find({"checked_vt": "true"}).sort("_id", -1)
        sites_count = mongo.db.sites.count_documents({"checked_vt": "true"})
        return render_template("alltime.html",
                sites=sites, sites_count = sites_count)

@app.route('/api/stats')
def api_stats():
    """API endpoint for dashboard statistics"""
    stats = {
        'total': mongo.db.sites.count_documents({"checked_vt": "true"}),
        'critical': mongo.db.sites.count_documents({"checked_vt": "true", "certphisher_score": {"$gt": 140}}),
        'high': mongo.db.sites.count_documents({"checked_vt": "true", "certphisher_score": {"$gte": 90, "$lt": 140}}),
        'medium': mongo.db.sites.count_documents({"checked_vt": "true", "certphisher_score": {"$gte": 80, "$lt": 90}}),
        'ca_stats': {}
    }

    # Get CA distribution
    pipeline = [
        {"$match": {"checked_vt": "true"}},
        {"$group": {"_id": "$certificate_authority", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    ca_results = list(mongo.db.sites.aggregate(pipeline))
    stats['ca_stats'] = {item['_id']: item['count'] for item in ca_results}

    return jsonify(stats)

@app.route('/settings')
def settings():
    """Brand monitoring configuration page"""
    brands = list(mongo.db.brands.find().sort("created_at", -1))
    return render_template('settings.html', brands=brands)

@app.route('/settings/add_brand', methods=['POST'])
def add_brand():
    """Add a new brand to monitor"""
    keyword = request.form.get('brand_keyword', '').strip().lower()
    name = request.form.get('brand_name', '').strip()
    reference_url = request.form.get('reference_url', '').strip()

    if not keyword:
        flash('Brand keyword is required', 'danger')
        return redirect('/settings')

    # Check if brand already exists
    if mongo.db.brands.find_one({"keyword": keyword}):
        flash(f'Brand "{keyword}" already exists', 'warning')
        return redirect('/settings')

    brand_data = {
        "keyword": keyword,
        "name": name or keyword.title(),
        "reference_url": reference_url,
        "logo_path": None,
        "reference_screenshot": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    # Handle logo upload
    if 'logo_file' in request.files:
        file = request.files['logo_file']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{keyword}_logo_{int(time.time())}.{file.filename.rsplit('.', 1)[1].lower()}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            brand_data['logo_path'] = filename

    mongo.db.brands.insert_one(brand_data)
    flash(f'Brand "{keyword}" added successfully!', 'success')
    return redirect('/settings')

@app.route('/settings/delete_brand/<brand_id>', methods=['POST'])
def delete_brand(brand_id):
    """Delete a brand from monitoring"""
    try:
        brand = mongo.db.brands.find_one({"_id": ObjectId(brand_id)})
        if brand:
            # Delete associated files
            if brand.get('logo_path'):
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], brand['logo_path']))
                except:
                    pass
            if brand.get('reference_screenshot'):
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], brand['reference_screenshot']))
                except:
                    pass

            mongo.db.brands.delete_one({"_id": ObjectId(brand_id)})
            flash('Brand deleted successfully', 'success')
        else:
            flash('Brand not found', 'danger')
    except:
        flash('Error deleting brand', 'danger')

    return redirect('/settings')

@app.route('/settings/capture_screenshot/<brand_id>', methods=['POST'])
def capture_screenshot(brand_id):
    """Capture screenshot of reference website"""
    try:
        brand = mongo.db.brands.find_one({"_id": ObjectId(brand_id)})
        if not brand or not brand.get('reference_url'):
            flash('Brand or reference URL not found', 'danger')
            return redirect('/settings')

        # Use headless Chrome to capture screenshot
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-software-rasterizer')

        # Set chromium binary location (for Docker)
        chrome_binary = os.environ.get('CHROME_BIN', '/usr/bin/chromium')
        if os.path.exists(chrome_binary):
            chrome_options.binary_location = chrome_binary
        elif os.path.exists('/usr/bin/chromium-browser'):
            chrome_options.binary_location = '/usr/bin/chromium-browser'

        try:
            # Try to use chromedriver from environment or standard locations
            chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')
            if chromedriver_path and os.path.exists(chromedriver_path):
                from selenium.webdriver.chrome.service import Service
                service = Service(executable_path=chromedriver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # Let Selenium find the driver automatically
                driver = webdriver.Chrome(options=chrome_options)

            driver.get(brand['reference_url'])
            time.sleep(3)  # Wait for page to load

            filename = secure_filename(f"{brand['keyword']}_screenshot_{int(time.time())}.png")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            driver.save_screenshot(filepath)
            driver.quit()

            # Delete old screenshot if exists
            if brand.get('reference_screenshot'):
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], brand['reference_screenshot']))
                except:
                    pass

            mongo.db.brands.update_one(
                {"_id": ObjectId(brand_id)},
                {"$set": {"reference_screenshot": filename, "updated_at": datetime.utcnow()}}
            )
            flash('Screenshot captured successfully!', 'success')
        except Exception as e:
            error_msg = str(e)
            # Provide helpful error message
            if 'chrome' in error_msg.lower() or 'driver' in error_msg.lower():
                flash(f'Chrome/Chromium not available in this environment. Screenshot feature requires Chrome. Error: {error_msg}', 'warning')
            else:
                flash(f'Error capturing screenshot: {error_msg}', 'danger')

    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')

    return redirect('/settings')

@app.route('/settings/refresh_screenshot/<brand_id>', methods=['POST'])
def refresh_screenshot(brand_id):
    """Refresh screenshot of reference website"""
    return capture_screenshot(brand_id)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/brands')
def api_brands():
    """API endpoint to get all monitored brands"""
    brands = list(mongo.db.brands.find({}, {'_id': 0}))
    return jsonify(brands)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
