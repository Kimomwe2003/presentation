"""Seed demo data: an admin superuser, three normal users, and products for each.

Data migration (run automatically by ``migrate``). Creates:

- Admin superuser:  kim@gmail.com / 12345678  (is_staff + is_superuser)
- Three identical normal demo users:
    demo1@gmail.com / 12345678
    demo2@gmail.com / 12345678
    demo3@gmail.com / 12345678
- 10 products for EACH normal user (30 total), across the demo categories,
  each with a real generated JPEG image (priced in TZS).

Idempotent: skips creation if the email already exists or the product name
already exists, so running ``migrate`` again won't duplicate data.
"""

import io
import random
import sys

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.core.files.images import ImageFile
from PIL import Image, ImageDraw

ADMIN_EMAIL = "kim@gmail.com"
ADMIN_PASSWORD = "12345678"
DEMO_PASSWORD = "12345678"

DEMO_USERS = [
    ("demo1@gmail.com", "Demo User One"),
    ("demo2@gmail.com", "Demo User Two"),
    ("demo3@gmail.com", "Demo User Three"),
]

PRODUCTS_PER_USER = 10

# (slug, name, item_names) — reused from the seed_products command catalog.
CATALOG = [
    (
        "electronics",
        "Electronics",
        [
            ("Samsung Galaxy A54 5G 256GB",
             "Like-new Samsung phone, single owner, battery 96%, screen pristine.", 500),
            ("JVC Wireless Bluetooth Headphones",
             "Over-ear noise-cancelling headphones with charging case, works.", 500),
            ("Canon EOS 2000D DSLR Camera Kit",
             "DSLR with 18-55mm lens, bag, spare battery and 32GB card.", 500),
        ],
    ),
    (
        "furniture",
        "Furniture",
        [
            ("Solid Oak Study Desk",
             "Solid hardwood desk with drawer, 120x60cm, lightly used.", 500),
            ("IKEA Grey Fabric 3-Seater Sofa",
             "Comfortable sofa, two years old, deep cleaned, smoke-free home.", 500),
        ],
    ),
    (
        "fashion",
        "Fashion",
        [
            ("Men's Leather Chelsea Boots (Size 43)",
             "Genuine leather boots, worn twice, shows like new.", 500),
            ("Women's Lightweight Denim Jacket (M)",
             "Classic denim jacket, excellent condition, zip works smoothly.", 500),
            ("Designer Canvas Backpack",
             "Water-resistant canvas rucksack with laptop sleeve, barely used.", 500),
        ],
    ),
    (
        "home-appliances",
        "Home Appliances",
        [
            ("Russell Hobbs Electric Kettle 1.7L",
             "Fast-boil stainless kettle, descale only, fully functional.", 500),
            ("2-Slice Toaster, Brushed Steel",
             "Toaster with 6 browning settings and a crumb tray.", 500),
            ("Tower Fan with Remote Control",
             "High-velocity standing fan, three speeds, oscillates, low noise.", 500),
        ],
    ),
    (
        "sports-fitness",
        "Sports & Fitness",
        [
            ("Adjustable Dumbbell Pair 20kg",
             "Compact adjustable dumbbells with stand, great home gym.", 500),
            ("Carbon Yoga Mat + Straps",
             "Extra-thick non-slip yoga mat with carry straps, like new.", 500),
            ("Mountain Bike, 26-inch, Black",
             "Rear suspension MTB, recently serviced, new brake pads.", 500),
        ],
    ),
    (
        "books",
        "Books",
        [
            ("Python Crash Course (3rd Edition)",
             "Softcover, few highlighted pages, otherwise clean.", 500),
            ("The Psychology of Money",
             "Hardcover, read once, near-perfect condition.", 500),
        ],
    ),
    (
        "toys",
        "Toys & Baby",
        [
            ("LEGO Classic Building Blocks (1000 pc)",
             "Complete set in original box, 6-99 years.", 500),
            ("Wooden Montessori Toddler Toy",
             "Educational stacking and sorting toy, all pieces present.", 500),
        ],
    ),
    (
        "garden-vehicles",
        "Garden & Vehicles",
        [
            ("Foldable Garden Wheelbarrow",
             "Heavy-duty 80L foldable wheelbarrow, minimal wear.", 500),
            ("Electric Scooter, 350W",
             "Foldable e-scooter, 25km range, charger included.", 500),
        ],
    ),
]

SHAPE_KINDS = ["circle", "triangle", "square", "diamond", "rect"]

_PALETTE = [
    {"bg": (240, 244, 248), "accent": (15, 23, 42), "ring": (100, 116, 139)},
    {"bg": (248, 250, 252), "accent": (71, 85, 105), "ring": (148, 163, 184)},
    {"bg": (241, 245, 249), "accent": (51, 65, 85), "ring": (203, 213, 225)},
    {"bg": (250, 250, 252), "accent": (30, 41, 59), "ring": (148, 163, 184)},
    {"bg": (243, 244, 246), "accent": (15, 23, 42), "ring": (100, 116, 139)},
]


def _draw_item(draw, size, theme, seed):
    rng = random.Random(seed)
    kind = SHAPE_KINDS[seed % len(SHAPE_KINDS)]
    margin = size * 0.24
    box = [margin, margin, size - margin, size - margin]
    fill = theme["accent"]
    if kind == "circle":
        draw.ellipse(box, fill=fill)
    elif kind == "triangle":
        cx = size / 2
        pts = [(cx, margin), (box[2], box[3]), (box[0], box[3])]
        draw.polygon(pts, fill=fill)
    elif kind == "square":
        draw.rectangle(box, fill=fill)
    elif kind == "diamond":
        cx, cy = size / 2, size / 2
        pts = [(cx, margin), (box[2], cy), (cx, box[3]), (box[0], cy)]
        draw.polygon(pts, fill=fill)
    else:
        draw.rounded_rectangle(
            [box[0], box[1] + (box[3] - box[1]) * 0.3, box[2], box[3]],
            radius=size * 0.04,
            fill=fill,
        )
    for _ in range(rng.randint(3, 5)):
        r = rng.randint(int(size * 0.03), int(size * 0.08))
        x = rng.randint(int(margin), int(size - margin))
        y = rng.randint(int(margin), int(size - margin))
        draw.ellipse([x - r, y - r, x + r, y + r], outline=theme["ring"], width=2)


def _make_image(seed):
    size = 800
    theme = _PALETTE[seed % len(_PALETTE)]
    img = Image.new("RGB", (size, size), theme["bg"])
    draw = ImageDraw.Draw(img)
    for i in range(0, size, 40):
        draw.line([(i, 0), (0, i)], fill=(255, 255, 255), width=1)
    _draw_item(draw, size, theme, seed)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    buf.seek(0)
    return buf


def _ensure_user(apps, email, password, is_staff=False, is_superuser=False, full_name=""):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    user = User.objects.filter(email=email).first()
    if user:
        return user
    # Historical models don't expose ``set_password``, so hash manually.
    user = User(
        email=email,
        password=make_password(password),
        is_staff=is_staff,
        is_superuser=is_superuser,
        is_active=True,
        username=email[:150],
    )
    user.save()
    # The app's post_save signal (Profile + Wallet) does NOT run inside a data
    # migration because only the historical models are loaded here. Create the
    # related rows explicitly to match what the plain ORM path would produce.
    Profile = apps.get_model("accounts", "Profile")
    Profile.objects.get_or_create(
        user=user, defaults={"full_name": full_name, "role": "ADMIN" if is_superuser else "BUYER"}
    )
    Wallet = apps.get_model("wallet", "Wallet")
    Wallet.objects.get_or_create(user=user)
    return user


def _seed_categories(apps):
    Category = apps.get_model("catalog", "Category")
    by_slug = {}
    for slug, cat_name, _items in CATALOG:
        cat, _ = Category.objects.get_or_create(slug=slug, defaults={"name": cat_name, "is_active": True})
        by_slug[slug] = cat
    return by_slug


def seed(apps, schema_editor):
    # Never seed demo data on the test database: the test runner creates a
    # fresh DB and runs every migration (including this data migration) before
    # running its fixtures, and the seeded users/categories/products collide
    # with test factories (same slugs/emails) and slow the run with 30 images.
    if "test" in sys.argv:
        return
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Product = apps.get_model("catalog", "Product")
    ProductImage = apps.get_model("catalog", "ProductImage")
    categories = _seed_categories(apps)

    # 1. Admin superuser.
    _ensure_user(apps, ADMIN_EMAIL, ADMIN_PASSWORD, is_staff=True, is_superuser=True, full_name="Admin")

    # 2. Three normal demo users + 10 products each.
    names_seen = set(Product.objects.values_list("name", flat=True))
    category_items = [
        (slug, item)
        for slug, _name, items in CATALOG
        for item in items
    ]
    for email, full_name in DEMO_USERS:
        user = _ensure_user(apps, email, DEMO_PASSWORD, full_name=full_name)
        seeded = 0
        for slug, (name, description, price) in category_items:
            if seeded >= PRODUCTS_PER_USER:
                break
            # Give the same product name a unique seller to avoid cross-user
            # collisions, and skip if already present.
            unique_name = f"{name} — {user.email.split('@')[0]}"
            if unique_name in names_seen:
                continue
            product = Product.objects.create(
                seller=user,
                category=categories[slug],
                name=unique_name,
                description=description,
                price=price,
                condition="LIKE_NEW",
                quantity=1,
                location="Dar es Salaam",
                status="ACTIVE",
            )
            names_seen.add(unique_name)
            seed_key = sum(ord(c) for c in unique_name)
            blob = _make_image(seed_key)
            img = ProductImage(product=product, is_primary=True, order=0)
            img.image.save(f"{product.pk}.jpg", ImageFile(blob), save=True)
            seeded += 1


def unseed(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Product = apps.get_model("catalog", "Product")
    Product.objects.filter(seller__email__in=[e for e, _ in DEMO_USERS]).delete()
    User.objects.filter(email__in=[ADMIN_EMAIL] + [e for e, _ in DEMO_USERS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_passwordresetcode"),
        ("catalog", "0002_alter_productimage_image"),
        ("wallet", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
