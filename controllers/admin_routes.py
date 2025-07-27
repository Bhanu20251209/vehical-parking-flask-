from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.models import *

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
count=0

# ========== DASHBOARD ==========
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('auth.login'))

    lots = ParkingLot.query.all()
    users = User.query.filter_by(role='user').all()
    return render_template('admin_dashboard.html', lots=lots, add_lot=add_lot,delete_lot=delete_lot,view_users=view_users,summery=summary)


# ========== ADD PARKING LOT ==========
@admin_bp.route('/add_lot', methods=['GET', 'POST'])
@login_required
def add_lot():
    if current_user.role != 'admin':
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        lot = ParkingLot(
            prime_location_name=request.form['prime_location_name'],
            address=request.form['address'],
            pin_code=request.form['pin_code'],
            price_per_hour=float(request.form['price_per_hour']),
            max_spots=int(request.form['max_spots'])
        )
        db.session.add(lot)
        db.session.flush()  

        for i in range(1, lot.max_spots + 1):
            spot = ParkingSpot(lot_id=lot.id, spot_number=i)
            db.session.add(spot)

        db.session.commit()
        flash('Parking lot added successfully.')
        return redirect(url_for('admin.dashboard'))

    return render_template('admin_add_parking_lot.html')


@admin_bp.route('/spot/<int:spot_id>')
@login_required
def view_spot_details(spot_id):
    if current_user.role != 'admin':
        flash("Unauthorized access.")
        return redirect(url_for('auth.login'))

    spot = ParkingSpot.query.get_or_404(spot_id)

    if spot.status != 'O':
        flash("Spot is not occupied.")
        return redirect(url_for('admin.dashboard'))

    # Get latest active reservation
    reservation = Reservation.query.filter_by(spot_id=spot.id, leaving_timestamp=None).first()

    if not reservation:
        flash("No active reservation found.")
        return redirect(url_for('admin.dashboard'))

    # Calculate estimated cost
    now = datetime.utcnow()
    duration = (now - reservation.parking_timestamp).total_seconds() / 3600
    estimated_cost = round(duration * reservation.cost_per_hour, 2)
    
    user=User.query.filter_by(id=reservation.user_id).first()

    return render_template("admin_spot_details.html",
                           spot=spot,
                           reservation=reservation,
                           user=user,
                           estimated_cost=estimated_cost,
                           now=now)

@admin_bp.route('/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
@login_required
def edit_lot(lot_id):
    if current_user.role != 'admin':
        return redirect(url_for('auth.login'))

    lot = ParkingLot.query.get_or_404(lot_id)
    current_spot_count = len(lot.parking_spots)

    if request.method == 'POST':
        lot.prime_location_name = request.form['prime_location_name']
        lot.address = request.form['address']
        lot.pin_code = request.form['pin_code']
        lot.price_per_hour = float(request.form['price_per_hour'])
        new_max_spots = int(request.form['max_spots'])

        if new_max_spots > current_spot_count:
            start_number = max([s.spot_number for s in lot.parking_spots], default=0)
            for i in range(1, new_max_spots - current_spot_count + 1):
                new_spot = ParkingSpot(
                    lot_id=lot.id,
                    spot_number=start_number + i
                )
                db.session.add(new_spot)


        elif new_max_spots < current_spot_count:
            to_delete = current_spot_count - new_max_spots
            available_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').all()
            safe_to_delete = [s for s in available_spots if not s.reservations]

            if len(safe_to_delete) >= to_delete:
                for spot in safe_to_delete[:to_delete]:
                    db.session.delete(spot)
            else:
                flash("Cannot reduce spots. Too many spots are occupied or reserved.")
                return redirect(url_for('admin.edit_lot', lot_id=lot.id))

        lot.max_spots = new_max_spots
        db.session.commit()

        remaining_spots = ParkingSpot.query.filter_by(lot_id=lot.id).order_by(ParkingSpot.id).all()
        for index, spot in enumerate(remaining_spots, start=1):
            spot.spot_number = index
        db.session.commit()

        flash("Parking lot updated successfully.")
        return redirect(url_for('admin.dashboard'))

    return render_template('admin_add_parking_lot.html', lot=lot)



@admin_bp.route('/occupied_spot/<int:spot_id>')
@login_required
def view_occupied_spot(spot_id):
    if current_user.role != 'admin':
        return redirect(url_for('auth.login'))
    reservation = Reservation.query.filter_by(spot_id=spot_id).order_by(Reservation.parking_timestamp.desc()).first()
    user = User.query.get(reservation.user_id)

    if not reservation or reservation.leaving_timestamp:
        flash("No active reservation found for this spot.")
        return redirect(url_for('admin.dashboard'))

    return render_template('admin_view_occupied_spot.html', reservation=reservation,user=user)


@admin_bp.route('/search', methods=['GET', 'POST'])
@login_required
def search_records():
    if current_user.role != 'admin':
        flash("Unauthorized")
        return redirect(url_for('auth.login'))

    users = []
    lots = []
    query = request.args.get('query', '').strip()

    if query:
       
        users = User.query.filter(
            (User.id.like(f"%{query}%")) |
            (User.email.ilike(f"%{query}%")) |
            (User.name.ilike(f"%{query}%"))
        ).all()

        lots = ParkingLot.query.filter(
            (ParkingLot.prime_location_name.ilike(f"%{query}%")) |
            (ParkingLot.address.ilike(f"%{query}%")) |
            (ParkingLot.pin_code.ilike(f"%{query}%"))
        ).all()

    return render_template("admin_search.html", users=users, lots=lots, query=query)



@admin_bp.route('/delete_lot/<int:lot_id>', methods=['GET', 'POST'])
@login_required
def delete_lot(lot_id):
    if current_user.role != 'admin':
        return redirect(url_for('auth.login'))

    lot = ParkingLot.query.get_or_404(lot_id)
    occupied_count = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()

    if occupied_count > 0:
        flash(f"Cannot delete lot. {occupied_count} spot(s) are still occupied.")
        return redirect(url_for('admin.dashboard'))
        
    for spot in lot.parking_spots:
      for s in spot.reservations:
          db.session.delete(s)
      db.session.delete(spot)

    db.session.delete(lot)
    db.session.commit()
    flash("Parking lot deleted successfully.")
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/view_users')
@login_required
def view_users():
    if current_user.role != 'admin':
        return redirect(url_for('auth.login'))
    users = User.query.filter_by(role='user').all()
    return render_template('admin_view_users.html', users=users)

@admin_bp.route('/summary')
@login_required
def summary():
    if current_user.role != 'admin':
        return redirect(url_for('auth.login'))

    lots = ParkingLot.query.all()

    lot_names = []
    revenues = []
    available_counts = []
    occupied_counts = []

    for lot in lots:
        lot_names.append(lot.prime_location_name)
        completed_res = Reservation.query.join(ParkingSpot).filter(
            ParkingSpot.lot_id == lot.id,
            Reservation.leaving_timestamp != None
        ).all()

        revenue = 0
        for r in completed_res:
            duration = (r.leaving_timestamp - r.parking_timestamp).total_seconds() / 3600
            revenue += round(duration * r.cost_per_hour, 2)
        revenues.append(round(revenue, 2))
        total_spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
        occupied = sum(1 for s in total_spots if s.status == 'O')
        available = sum(1 for s in total_spots if s.status == 'A')
        occupied_counts.append(occupied)
        available_counts.append(available)
        
    

    return render_template("admin_summary.html", lot_names=lot_names,revenues=revenues, occupied_counts=occupied_counts,available_counts=available_counts)
