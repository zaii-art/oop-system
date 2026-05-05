from flask import Flask, request, render_template, redirect, url_for, flash
from datetime import datetime
from abc import ABC, abstractmethod
import pytz

app = Flask(__name__)
app.secret_key = "secret123"


class BaseEntity(ABC):
    def __init__(self, id):
        self._id = id

    @property
    def id(self):
        return self._id

    @abstractmethod
    def to_dict(self):
        pass

    @abstractmethod
    def get_status(self):
        pass


class Discount(BaseEntity):
    def __init__(self, id, name, dtype, value, start, end, apply_type, product_id=None, category=None):
        super().__init__(id)
        self._name = name
        self._type = dtype
        self._value = float(value)
        self._start = start
        self._end = end
        self._apply_type = apply_type
        self._product_id = product_id
        self._category = category

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, value):
        self._type = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = v

    @property
    def start(self):
        return self._start

    @start.setter
    def start(self, v):
        self._start = v

    @property
    def end(self):
        return self._end

    @end.setter
    def end(self, v):
        self._end = v

    @property
    def apply_type(self):
        return self._apply_type

    @apply_type.setter
    def apply_type(self, v):
        self._apply_type = v

    @property
    def product_id(self):
        return self._product_id

    @product_id.setter
    def product_id(self, v):
        self._product_id = v

    @property
    def category(self):
        return self._category

    @category.setter
    def category(self, v):
        self._category = v

    @property
    def start_dt(self):
        return datetime.strptime(self._start, "%Y-%m-%dT%H:%M")

    @property
    def end_dt(self):
        return datetime.strptime(self._end, "%Y-%m-%dT%H:%M")

    def get_status(self):
        manila_tz = pytz.timezone('Asia/Manila')
        now = datetime.now(manila_tz).replace(tzinfo=None)
        if now < self.start_dt:
            return "Upcoming"
        elif now > self.end_dt:
            return "Expired"
        else:
            return "Active"

    def calculate_discount(self, price):
        if self._type == "Percentage":
            return price * self._value / 100
        return self._value

    def to_dict(self):
        return {
            "id": self._id,
            "name": self._name,
            "type": self._type,
            "value": self._value,
            "start": self._start,
            "end": self._end,
            "apply_type": self._apply_type,
            "product_id": self._product_id,
            "category": self._category,
            "status": self.get_status(),
            "start_readable": self.start_dt.strftime("%B %d, %Y - %I:%M %p"),
            "end_readable": self.end_dt.strftime("%B %d, %Y - %I:%M %p"),
        }


class PercentageDiscount(Discount):
    def __init__(self, id, name, value, start, end, apply_type, product_id=None, category=None):
        super().__init__(id, name, "Percentage", value, start, end, apply_type, product_id, category)

    def calculate_discount(self, price):
        return round(price * self._value / 100, 2)

    def to_dict(self):
        data = super().to_dict()
        data["discount_label"] = f"{self._value}% OFF"
        return data


class FixedDiscount(Discount):
    def __init__(self, id, name, value, start, end, apply_type, product_id=None, category=None):
        super().__init__(id, name, "Fixed", value, start, end, apply_type, product_id, category)

    def calculate_discount(self, price):
        return round(min(self._value, price), 2)

    def to_dict(self):
        data = super().to_dict()
        data["discount_label"] = f"P{self._value:.2f} OFF"
        return data


class DiscountFactory:
    @staticmethod
    def create(id, name, dtype, value, start, end, apply_type, product_id=None, category=None):
        if dtype == "Percentage":
            return PercentageDiscount(id, name, value, start, end, apply_type, product_id, category)
        else:
            return FixedDiscount(id, name, value, start, end, apply_type, product_id, category)


class Product(BaseEntity):
    def __init__(self, id, name, price, category):
        super().__init__(id)
        self._name = name
        self._price = float(price)
        self._category = category

    @property
    def name(self):
        return self._name

    @property
    def price(self):
        return self._price

    @property
    def category(self):
        return self._category

    def get_status(self):
        return "Available" if self._price > 0 else "Unavailable"

    def get_final_price(self, discount_list):
        final_price = self._price
        active_discount = None

        for d in discount_list:
            if d.get_status() == "Active":
                applies = (
                    (d.apply_type == "product" and d.product_id == self._id) or
                    (d.apply_type == "category" and d.category == self._category)
                )
                if applies:
                    deduction = d.calculate_discount(self._price)
                    final_price = self._price - deduction
                    active_discount = d
                    break

        return max(round(final_price, 2), 0), active_discount

    def to_dict(self):
        return {
            "id": self._id,
            "name": self._name,
            "price": self._price,
            "category": self._category,
            "status": self.get_status(),
        }


class User:
    def __init__(self, username, password, role):
        self._username = username
        self._password = password
        self._role = role

    @property
    def username(self):
        return self._username

    @property
    def role(self):
        return self._role

    def check_password(self, password):
        return self._password == password


class ReportService:
    def __init__(self, discount_list):
        self._discounts = discount_list

    def get_stats(self):
        stats = {
            "total": len(self._discounts),
            "active": 0, "upcoming": 0, "expired": 0,
            "percentage_count": 0, "fixed_count": 0,
            "product_target": 0, "category_target": 0,
            "total_perc_val": 0, "total_fixed_val": 0
        }

        for d in self._discounts:
            status = d.get_status()
            if status == "Upcoming":
                stats["upcoming"] += 1
            elif status == "Expired":
                stats["expired"] += 1
            else:
                stats["active"] += 1

            if d.type == "Percentage":
                stats["percentage_count"] += 1
                stats["total_perc_val"] += d.value
            else:
                stats["fixed_count"] += 1
                stats["total_fixed_val"] += d.value

            if d.apply_type == "product":
                stats["product_target"] += 1
            else:
                stats["category_target"] += 1

        avg_perc = round(stats["total_perc_val"] / stats["percentage_count"], 1) if stats["percentage_count"] > 0 else 0
        avg_fixed = round(stats["total_fixed_val"] / stats["fixed_count"], 1) if stats["fixed_count"] > 0 else 0

        total_targets = stats["product_target"] + stats["category_target"]
        prod_p = round((stats["product_target"] / total_targets) * 100) if total_targets > 0 else 0
        cat_p = 100 - prod_p if total_targets > 0 else 0

        return {
            "stats": stats,
            "avg_perc": avg_perc,
            "avg_fixed": avg_fixed,
            "prod_p": prod_p,
            "cat_p": cat_p
        }


users = {
    "HARI": User("HARI", "king", "admin"),
    "ALIPIN": User("ALIPIN", "slave", "staff"),
}

products = {
    "p1": Product("p1", "T-Shirt", 200, "Clothing"),
    "p2": Product("p2", "Shoes", 500, "Footwear"),
    "p3": Product("p3", "Cap", 300, "Accessories"),
    "p4": Product("p4", "Jacket", 500, "Clothing"),
    "p5": Product("p5", "Knife", 700, "Kitchen"),
    "p6": Product("p6", "Short", 150, "Clothing"),
    "p7": Product("p7", "Baggy Pants", 250, "Clothing"),
}

discounts = {}
discount_id_counter = 1
categories = ["Clothing", "Footwear", "Accessories", "Kitchen"]


def build_product_list(discount_objs):
    product_list = []
    for p in products.values():
        final, disc = p.get_final_price(discount_objs)
        product_list.append({
            "name": p.name,
            "original": p.price,
            "category": p.category,
            "status": p.get_status(),
            "final": final,
            "saved": round(p.price - final, 2),
            "discount": disc.to_dict() if disc else None,
        })
    return product_list


@app.route("/")
def intro():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = users.get(username)
        if user and user.check_password(password):
            return redirect(url_for("admin" if user.role == "admin" else "staff"))
        else:
            message = "Invalid username or password"
    return render_template("login.html", message=message)


@app.route("/register", methods=["GET", "POST"])
def register():
    message, message_type = "", ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users:
            message, message_type = "Username already exists.", "error"
        else:
            users[username] = User(username, password, "staff")
            message, message_type = "Account successfully created.", "success"
    return render_template("register.html", message=message, message_type=message_type)


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/staff")
def staff():
    return render_template("staff.html")


@app.route("/discounts")
def discounts_page():
    dict_discounts = {k: v.to_dict() for k, v in discounts.items()}
    return render_template("discounts.html", discounts=dict_discounts, products=products, categories=categories)


@app.route("/create_discount", methods=["POST"])
def create_discount():
    global discount_id_counter
    try:
        name = request.form["name"]
        dtype = request.form["type"]
        value = float(request.form["value"])
        start = request.form["start"]
        end = request.form["end"]
        apply_type = request.form["apply_type"]
        product_id = request.form.get("product_id")
        category = request.form.get("category")

        if value <= 0:
            flash("Discount value must be greater than 0.", "error")
            return redirect(url_for("discounts_page"))

        if dtype == "Percentage" and value > 100:
            flash("Percentage discount cannot exceed 100%.", "error")
            return redirect(url_for("discounts_page"))

        if end <= start:
            flash("End date must be later than Start date.", "error")
            return redirect(url_for("discounts_page"))

        disc_id = f"disc_{discount_id_counter:03d}"
        new_disc = DiscountFactory.create(disc_id, name, dtype, value, start, end, apply_type, product_id, category)
        discounts[disc_id] = new_disc
        discount_id_counter += 1
        flash("Discount created successfully!", "success")

    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("discounts_page"))


@app.route("/update_discount/<discount_id>", methods=["POST"])
def update_discount(discount_id):
    if discount_id not in discounts:
        flash("Discount not found.", "error")
        return redirect(url_for("discounts_page"))

    d = discounts[discount_id]
    status = d.get_status()

    if status == "Expired":
        flash("Expired discounts cannot be edited.", "error")
        return redirect(url_for("discounts_page"))

    d.name = request.form["name"]

    if status == "Upcoming":
        try:
            val = float(request.form["value"])
            dtype = request.form["type"]

            if dtype == "Percentage" and val > 100:
                flash("Percentage cannot exceed 100%.", "error")
                return redirect(url_for("discounts_page"))

            d.type = dtype
            d.value = val
            d.start = request.form["start"]
            d.end = request.form["end"]
            d.apply_type = request.form["apply_type"]
            d.product_id = request.form.get("product_id")
            d.category = request.form.get("category")

            flash("Discount updated successfully!", "success")
        except:
            flash("Invalid input data.", "error")
    else:
        flash("Active discount: only the name was updated.", "success")

    return redirect(url_for("discounts_page"))


@app.route("/delete_discount/<discount_id>")
def delete_discount(discount_id):
    if discount_id in discounts:
        d = discounts[discount_id]
        if d.get_status() == "Expired":
            flash("Expired discounts cannot be deleted.", "error")
        else:
            del discounts[discount_id]
            flash("Discount deleted.", "success")
    return redirect(url_for("discounts_page"))


@app.route("/products")
def product_page():
    product_list = build_product_list(list(discounts.values()))
    return render_template("products.html", products=product_list, categories=categories)


@app.route("/staff_products")
def staff_product_page():
    product_list = build_product_list(list(discounts.values()))
    return render_template("staff_products_view.html", products=product_list, categories=categories)


@app.route("/staff_discounts")
def staff_discounts_page():
    dict_discounts = {k: v.to_dict() for k, v in discounts.items()}
    return render_template("staff_discounts_view.html", discounts=dict_discounts, products=products)


@app.route("/daily_reports")
def daily_reports_page():
    report = ReportService(list(discounts.values()))
    data = report.get_stats()
    return render_template("reports.html", **data)


@app.route("/staff_reports")
def staff_reports_page():
    report = ReportService(list(discounts.values()))
    data = report.get_stats()
    return render_template("staff_reports.html", **data)


if __name__ == "__main__":
    app.run(debug=True)
