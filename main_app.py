from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "parking_app.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(15), nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    reservations = db.relationship('Reservation', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'

class ParkingLot(db.Model):
    __tablename__ = 'parking_lots'
    
    id = db.Column(db.Integer, primary_key=True)
    prime_location_name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    address = db.Column(db.Text, nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    maximum_spots = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    parking_spots = db.relationship('ParkingSpot', backref='lot', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ParkingLot {self.prime_location_name}>'

class ParkingSpot(db.Model):
    __tablename__ = 'parking_spots'
    
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lots.id'), nullable=False)
    status = db.Column(db.String(1), default='A', nullable=False)  # 'A' = Available, 'O' = Occupied
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    reservations = db.relationship('Reservation', backref='spot', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ParkingSpot {self.id} - {self.status}>'

class Reservation(db.Model):
    __tablename__ = 'reservations'
    
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spots.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parking_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    leaving_timestamp = db.Column(db.DateTime, nullable=True)
    parking_cost = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='active', nullable=False)  # 'active', 'completed'
    
    def __repr__(self):
        return f'<Reservation {self.id} - {self.status}>'

# Database initialization
def init_db():
    """Initialize database with tables and default admin user"""
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Create admin user if not exists
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_password = generate_password_hash('admin123')
            admin = User(
                username='admin',
                password=admin_password,
                email='admin@parking.com',
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")

# Routes
@app.route('/')
def index():
    return render_template('index.html')

# class Login(Resource) :
#     def get(self):
#         #pass

# api.add_resource(Login , "/api/login")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        phone = request.form['phone']
        
        # Check if user exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists')
            return render_template('register.html')
        
        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            password=hashed_password,
            email=email,
            phone=phone
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    # Get parking lots with spot counts using SQLAlchemy
    lots_data = []
    lots = ParkingLot.query.all()
    
    for lot in lots:
        total_spots = len(lot.parking_spots)
        available_spots = len([spot for spot in lot.parking_spots if spot.status == 'A'])
        occupied_spots = len([spot for spot in lot.parking_spots if spot.status == 'O'])
        
        lots_data.append({
            'id': lot.id,
            'prime_location_name': lot.prime_location_name,
            'address': lot.address,
            'pin_code': lot.pin_code,
            'price': lot.price,
            'maximum_spots': lot.maximum_spots,
            'total_spots': total_spots,
            'available_spots': available_spots,
            'occupied_spots': occupied_spots,
            'created_at': lot.created_at
        })
    
    # Get total users (non-admin)
    total_users = User.query.filter_by(is_admin=False).count()
    
    # Get active reservations
    active_reservations = Reservation.query.filter_by(status='active').count()
    
    return render_template('admin_dashboard.html', 
                         lots=lots_data, 
                         total_users=total_users,
                         active_reservations=active_reservations)

@app.route('/user_dashboard')
def user_dashboard():
    if not session.get('user_id') or session.get('is_admin'):
        return redirect(url_for('login'))
    
    # Get available parking lots
    lots_data = []
    lots = ParkingLot.query.all()
    
    for lot in lots:
        available_spots = len([spot for spot in lot.parking_spots if spot.status == 'A'])
        total_spots = len(lot.parking_spots)
        
        if available_spots > 0:  # Only show lots with available spots
            lots_data.append({
                'id': lot.id,
                'prime_location_name': lot.prime_location_name,
                'address': lot.address,
                'pin_code': lot.pin_code,
                'price': lot.price,
                'total_spots': total_spots,
                'available_spots': available_spots
            })
    
    # Get user's current reservations
    user_reservations = db.session.query(
        Reservation, ParkingSpot, ParkingLot
    ).join(
        ParkingSpot, Reservation.spot_id == ParkingSpot.id
    ).join(
        ParkingLot, ParkingSpot.lot_id == ParkingLot.id
    ).filter(
        Reservation.user_id == session['user_id'],
        Reservation.status == 'active'
    ).all()
    
    # Get user's parking history
    parking_history = db.session.query(
        Reservation, ParkingSpot, ParkingLot
    ).join(
        ParkingSpot, Reservation.spot_id == ParkingSpot.id
    ).join(
        ParkingLot, ParkingSpot.lot_id == ParkingLot.id
    ).filter(
        Reservation.user_id == session['user_id']
    ).order_by(
        Reservation.parking_timestamp.desc()
    ).limit(10).all()
    for i in parking_history:
        print(i)
    return render_template('user_dashboard.html', 
                         lots=lots_data, 
                         user_reservations=user_reservations,
                         parking_history=parking_history)

@app.route('/create_lot', methods=['GET', 'POST'])
def create_lot():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        location_name = request.form['location_name']
        price = float(request.form['price'])
        address = request.form['address']
        pin_code = request.form['pin_code']
        max_spots = int(request.form['max_spots'])
        
        # Create parking lot
        new_lot = ParkingLot(
            prime_location_name=location_name,
            price=price,
            address=address,
            pin_code=pin_code,
            maximum_spots=max_spots
        )
        
        db.session.add(new_lot)
        db.session.flush()  # Get the ID of the newly created lot
        
        # Create parking spots for this lot
        for i in range(max_spots):
            new_spot = ParkingSpot(
                lot_id=new_lot.id,
                status='A'
            )
            db.session.add(new_spot)
        
        db.session.commit()
        
        flash('Parking lot created successfully!')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('create_lot.html')

@app.route('/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
def edit_lot(lot_id):
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    lot = ParkingLot.query.get_or_404(lot_id)
    
    if request.method == 'POST':
        location_name = request.form['location_name']
        price = float(request.form['price'])
        address = request.form['address']
        pin_code = request.form['pin_code']
        max_spots = int(request.form['max_spots'])
        
        # Get current spot count
        current_spots = len(lot.parking_spots)
        
        # Update lot details
        lot.prime_location_name = location_name
        lot.price = price
        lot.address = address
        lot.pin_code = pin_code
        lot.maximum_spots = max_spots
        
        # Adjust parking spots if needed
        if max_spots > current_spots:
            # Add more spots
            for i in range(max_spots - current_spots):
                new_spot = ParkingSpot(lot_id=lot.id, status='A')
                db.session.add(new_spot)
        elif max_spots < current_spots:
            # Remove excess spots (only if they're available)
            available_spots = [spot for spot in lot.parking_spots if spot.status == 'A']
            spots_to_remove = current_spots - max_spots
            
            if len(available_spots) >= spots_to_remove:
                for i in range(spots_to_remove):
                    db.session.delete(available_spots[i])
            else:
                flash('Cannot reduce spots: Some spots are occupied')
                return redirect(url_for('edit_lot', lot_id=lot_id))
        
        db.session.commit()
        
        flash('Parking lot updated successfully!')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('edit_lot.html', lot=lot)

@app.route('/delete_lot/<int:lot_id>')
def delete_lot(lot_id):
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    lot = ParkingLot.query.get_or_404(lot_id)
    
    # Check if all spots are available
    occupied_spots = [spot for spot in lot.parking_spots if spot.status == 'O']
    
    if occupied_spots:
        flash('Cannot delete lot: Some spots are occupied')
    else:
        # SQLAlchemy will handle cascade deletion of spots and reservations
        db.session.delete(lot)
        db.session.commit()
        flash('Parking lot deleted successfully!')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/book_spot/<int:lot_id>')
def book_spot(lot_id):
    if not session.get('user_id') or session.get('is_admin'):
        return redirect(url_for('login'))
    
    lot = ParkingLot.query.get_or_404(lot_id)
    
    # Find first available spot
    available_spot = next((spot for spot in lot.parking_spots if spot.status == 'A'), None)
    
    if not available_spot:
        flash('No available spots in this parking lot')
        return redirect(url_for('user_dashboard'))
    
    # Book the spot
    available_spot.status = 'O'
    
    # Create reservation
    new_reservation = Reservation(
        spot_id=available_spot.id,
        user_id=session['user_id'],
        status='active'
    )
    
    db.session.add(new_reservation)
    db.session.commit()
    
    flash('Parking spot booked successfully!')
    return redirect(url_for('user_dashboard'))

@app.route('/release_spot/<int:reservation_id>')
def release_spot(reservation_id):
    if not session.get('user_id') or session.get('is_admin'):
        return redirect(url_for('login'))
    
    reservation = Reservation.query.filter_by(
        id=reservation_id, 
        user_id=session['user_id']
    ).first_or_404()
    
    # Get the spot and lot information
    spot = reservation.spot
    lot = spot.lot
    
    # Calculate parking cost (simplified - per hour)
    parking_time = datetime.utcnow() - reservation.parking_timestamp
    hours = max(1, int(parking_time.total_seconds() / 3600))  # Minimum 1 hour
    cost = hours * lot.price
    
    # Update reservation
    reservation.leaving_timestamp = datetime.utcnow()
    reservation.parking_cost = cost
    reservation.status = 'completed'
    
    # Update spot status
    spot.status = 'A'
    
    db.session.commit()
    
    flash(f'Spot released successfully! Total cost: ₹{cost:.2f}')
    return redirect(url_for('user_dashboard'))

@app.route('/view_users')
def view_users():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    # Get all non-admin users with their booking counts
    users_data = []
    users = User.query.filter_by(is_admin=False).all()
    
    for user in users:
        total_bookings = len(user.reservations)
        users_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone': user.phone,
            'total_bookings': total_bookings,
            'created_at': user.created_at
        })
    
    return render_template('view_users.html', users=users_data)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/parking_data')
def parking_data():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    if session.get('is_admin'):
        # Admin data - parking lots overview
        data = []
        lots = ParkingLot.query.all()
        
        for lot in lots:
            total_spots = len(lot.parking_spots)
            available_spots = len([spot for spot in lot.parking_spots if spot.status == 'A'])
            occupied_spots = len([spot for spot in lot.parking_spots if spot.status == 'O'])
            
            data.append({
                'name': lot.prime_location_name,
                'total': total_spots,
                'available': available_spots,
                'occupied': occupied_spots
            })
    else:
        # User data - monthly booking statistics
        user_reservations = Reservation.query.filter_by(user_id=session['user_id']).all()
        
        # Group by month
        monthly_data = {}
        for reservation in user_reservations:
            month = reservation.parking_timestamp.strftime('%Y-%m')
            if month not in monthly_data:
                monthly_data[month] = {'bookings': 0, 'total_cost': 0}
            
            monthly_data[month]['bookings'] += 1
            if reservation.parking_cost:
                monthly_data[month]['total_cost'] += reservation.parking_cost
        
        # Convert to list format
        data = []
        for month in sorted(monthly_data.keys(), reverse=True)[:6]:  # Last 6 months
            data.append({
                'month': month,
                'bookings': monthly_data[month]['bookings'],
                'total_cost': monthly_data[month]['total_cost']
            })
    
    return jsonify(data)

if __name__ == '__main__':
    # Initialize database on first run
    if not os.path.exists(os.path.join(basedir, 'parking_app.db')):
        init_db()
        print("Database initialized successfully!")
    
    app.run(debug=True)
