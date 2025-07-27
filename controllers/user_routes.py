from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.models import ParkingLot, ParkingSpot, Reservation
from models.models import db
from datetime import datetime

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard', methods=['GET'])
@login_required
def user_dashboard():
    if current_user.role != 'user':
        flash("Unauthorized")
        return redirect(url_for('auth.login'))

    search_term = request.args.get('search', '').strip()
    parking_lots = []

    if search_term:
        matched_lots = ParkingLot.query.filter(
            (ParkingLot.address.ilike(f"%{search_term}%")) |
            (ParkingLot.pin_code.ilike(f"%{search_term}%"))
        ).all()
        print(matched_lots)

        for lot in matched_lots:
            available = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').count()
            if available > 0:
                lot.available = available
                parking_lots.append(lot)
    recent = Reservation.query.filter_by(user_id=current_user.id).order_by(Reservation.parking_timestamp.desc()).limit(5).all()

    return render_template("user_dashboard.html", recent=recent, parking_lots=parking_lots, search_term=search_term)

@user_bp.route('/release', methods=['POST'])
@login_required
def release_parking():
    res_id = request.form['reservation_id']
    res = Reservation.query.get(res_id)

    if res and res.user_id == current_user.id and not res.leaving_timestamp:
        res.leaving_timestamp = datetime.utcnow()
        res.spot.status = 'A'
        db.session.commit()
        flash("Parking spot released.")
    else:
        flash("Invalid release request.")

    return redirect(url_for('user.user_dashboard'))


@user_bp.route('/release/<int:res_id>', methods=['GET', 'POST'])
@login_required
def release_spot(res_id):
    reservation = Reservation.query.get_or_404(res_id)

    if reservation.user_id != current_user.id or reservation.leaving_timestamp:
        flash("Invalid or already released reservation.")
        return redirect(url_for('user.user_dashboard'))

    if request.method == 'POST':
        release_time = datetime.utcnow()
        duration = (release_time - reservation.parking_timestamp).total_seconds() / 3600  
        duration = max(duration, 0.1)  

        cost = round(duration * reservation.cost_per_hour, 2)

        reservation.leaving_timestamp = release_time
        reservation.spot.status = 'A'

        db.session.commit()
        flash(f"Spot released. Total cost: ₹{cost}")
        return redirect(url_for('user.user_dashboard'))

    return render_template("user_release_parking.html", reservation=reservation, now= datetime.utcnow())


@user_bp.route('/book', methods=['GET', 'POST'])
@login_required
def book_spot():
    if current_user.role != 'user':
        flash("Unauthorized")
        return redirect(url_for('auth.login'))

    if request.method == 'GET':
        lot_id = request.args.get('lot_id')
        lot = ParkingLot.query.get(lot_id)
        print(lot.id,lot.prime_location_name)
        spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
        print(spots)
        return render_template("user_book_spot.html", lot=lot, spots=spots)

    lot_id= request.form['lot_id']
    spot_id = request.form['spot_id']
    vehicle_number = request.form['vehicle_number']
    spot = ParkingSpot.query.filter_by(spot_number=spot_id, lot_id=lot_id).first()

    if not spot or spot.status == 'O':
        flash("Selected spot is already occupied.")
        return redirect(url_for('user.user_dashboard'))

    spot.status = 'O'
    reservation = Reservation(
        spot_id=spot.id,
        user_id=current_user.id,
        vehicle_number=vehicle_number,
        parking_timestamp=datetime.utcnow(),
        cost_per_hour=spot.lot.price_per_hour
    )

    db.session.add(reservation)
    db.session.commit()

    flash(f"Spot #{spot.id} successfully reserved.")
    return redirect(url_for('user.user_dashboard'))

@user_bp.route('/summary/<int:user_id>')
@login_required
def user_time_summary(user_id):
    if current_user.id != user_id or current_user.role != 'user':
        flash("Unauthorized")
        return redirect(url_for('auth.login'))

    from sqlalchemy import func
    reservations = db.session.query(
        ParkingLot.prime_location_name,
        Reservation.parking_timestamp,
        Reservation.leaving_timestamp,
        Reservation.cost_per_hour
    ).join(ParkingSpot, ParkingSpot.id == Reservation.spot_id) \
     .join(ParkingLot, ParkingLot.id == ParkingSpot.lot_id) \
     .filter(Reservation.user_id == user_id, Reservation.leaving_timestamp != None) \
     .all()

    usage = {}

    for lot_name, start, end, rate in reservations:
        hours = (end - start).total_seconds() / 3600
        usage[lot_name] = usage.get(lot_name, 0) + round(hours, 2)

    lot_names = list(usage.keys())
    total_hours = list(usage.values())
    
    print(lot_names,total_hours)
    return render_template("user_summary.html", lot_names=lot_names, total_hours=total_hours)
