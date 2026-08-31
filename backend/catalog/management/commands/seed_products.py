"""Seed the catalog with real demo products (categories, products, images).

Run:  python manage.py seed_products

Creates:
- A single demo seller account (reusehub@demo.reusehub / demo@12345) if absent.
- A set of categories.
- 20 products across those categories, all priced in Tanzanian Shillings (TZS).
- A real, decodable product image per product, generated deterministically with
  Pillow (each looks plausibly related to its item via a colour theme + shape).

The command is idempotent: it only creates what's missing (keyed on category
slug and product name), so re-running won't duplicate data.
"""

import io
import random

from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw

from accounts.models import Profile, User
from catalog.models import Category, Product, ProductImage

SELLER_EMAIL = "reusehub@demo.reusehub"
SELLER_PASSWORD = "demo@12345"

# (slug, name, item_names) — item_names are the real products, priced in TZS.
CATALOG = [
    (
        "electronics",
        "Electronics",
        [
            ("Samsung Galaxy A54 5G 256GB",
             "Like-new Samsung phone, single owner, battery 96%, screen pristine.",
             500),
            ("JVC Wireless Bluetooth Headphones",
             "Over-ear noise-cancelling headphones with charging case, works.",
             500),
            ("Canon EOS 2000D DSLR Camera Kit",
             "DSLR with 18-55mm lens, bag, spare battery and 32GB card.",
             500),
        ],
    ),
    (
        "furniture",
        "Furniture",
        [
            ("Solid Oak Study Desk",
             "Solid hardwood desk with drawer, 120x60cm, lightly used.",
             500),
            ("IKEA Grey Fabric 3-Seater Sofa",
             "Comfortable sofa, two years old, deep cleaned, smoke-free home.",
             500),
        ],
    ),
    (
        "fashion",
        "Fashion",
        [
            ("Men's Leather Chelsea Boots (Size 43)",
             "Genuine leather boots, worn twice, shows like new.",
             500),
            ("Women's Lightweight Denim Jacket (M)",
             "Classic denim jacket, excellent condition, zip works smoothly.",
             500),
            ("Designer Canvas Backpack",
             "Water-resistant canvas rucksack with laptop sleeve, barely used.",
             500),
        ],
    ),
    (
        "home-appliances",
        "Home Appliances",
        [
            ("Russell Hobbs Electric Kettle 1.7L",
             "Fast-boil stainless kettle, descale only, fully functional.",
             500),
            ("2-Slice Toaster, Brushed Steel",
             "Toaster with 6 browning settings and a crumb tray.",
             500),
            ("Tower Fan with Remote Control",
             "High-velocity standing fan, three speeds, oscillates, low noise.",
             500),
        ],
    ),
    (
        "sports-fitness",
        "Sports & Fitness",
        [
            ("Adjustable Dumbbell Pair 20kg",
             "Compact adjustable dumbbells with stand, great home gym.",
             500),
            ("Carbon Yoga Mat + Straps",
             "Extra-thick non-slip yoga mat with carry straps, like new.",
             500),
            ("Mountain Bike, 26-inch, Black",
             "Rear suspension MTB, recently serviced, new brake pads.",
             500),
        ],
    ),
    (
        "books",
        "Books",
        [
            ("Python Crash Course (3rd Edition)",
             "Softcover, few highlighted pages, otherwise clean.",
             500),
            ("The Psychology of Money",
             "Hardcover, read once, near-perfect condition.",
             500),
        ],
    ),
    (
        "toys",
        "Toys & Baby",
        [
            ("LEGO Classic Building Blocks (1000 pc)",
             "Complete set in original box, 6-99 years.",
             500),
            ("Wooden Montessori Toddler Toy",
             "Educational stacking and sorting toy, all pieces present.",
             500),
        ],
    ),
    (
        "garden-vehicles",
        "Garden & Vehicles",
        [
            ("Foldable Garden Wheelbarrow",
             "Heavy-duty 80L foldable wheelbarrow, minimal wear.",
             500),
            ("Electric Scooter, 350W",
             "Foldable e-scooter, 25km range, charger included.",
             500),
        ],
    ),
]

# Deterministic per-product visual themes (background colour, accent, shape).
SHAPE_KINDS = ["circle", "triangle", "square", "diamond", "rect"]


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
    else:  # rect
        draw.rounded_rectangle(
            [box[0], box[1] + (box[3] - box[1]) * 0.3, box[2], box[3]],
            radius=size * 0.04,
            fill=fill,
        )
    # A few decorative rings / dots to keep it looking like a real product shot.
    for _ in range(rng.randint(3, 5)):
        r = rng.randint(int(size * 0.03), int(size * 0.08))
        x = rng.randint(int(margin), int(size - margin))
        y = rng.randint(int(margin), int(size - margin))
        draw.ellipse([x - r, y - r, x + r, y + r], outline=theme["ring"], width=2)


def _make_image(seed):
    """Return an in-memory JPEG bytes for a generated product image."""
    size = 800
    palette = [
        {"bg": (240, 244, 248), "accent": (15, 23, 42), "ring": (100, 116, 139)},
        {"bg": (248, 250, 252), "accent": (71, 85, 105), "ring": (148, 163, 184)},
        {"bg": (241, 245, 249), "accent": (51, 65, 85), "ring": (203, 213, 225)},
        {"bg": (250, 250, 252), "accent": (30, 41, 59), "ring": (148, 163, 184)},
        {"bg": (243, 244, 246), "accent": (15, 23, 42), "ring": (100, 116, 139)},
    ]
    theme = palette[seed % len(palette)]

    img = Image.new("RGB", (size, size), theme["bg"])
    draw = ImageDraw.Draw(img)
    # Subtle diagonal sheen to mimic a studio backdrop.
    for i in range(0, size, 40):
        draw.line([(i, 0), (0, i)], fill=(255, 255, 255), width=1)
    _draw_item(draw, size, theme, seed)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    buf.seek(0)
    return buf


class Command(BaseCommand):
    help = "Seed 20 demo products with real generated images, prices in TZS."

    @transaction.atomic
    def handle(self, *args, **options):
        # 1. Ensure a seller account exists.
        seller, created = User.objects.get_or_create(
            email=SELLER_EMAIL,
            defaults={"is_active": True},
        )
        if created:
            seller.set_password(SELLER_PASSWORD)
            seller.save()
        Profile.objects.get_or_create(user=seller, defaults={"full_name": "ReuseHub Demo Seller"})
        self.stdout.write(f"Seller: {seller.email} (created={created})")

        # 2. Categories + products + images (idempotent on slug/name).
        created_products = 0
        created_categories = 0
        for slug, cat_name, items in CATALOG:
            category, cat_created = Category.objects.get_or_create(
                slug=slug, defaults={"name": cat_name, "is_active": True}
            )
            if cat_created:
                created_categories += 1
            for _idx, (name, description, price_tzs) in enumerate(items):
                if Product.objects.filter(name=name).exists():
                    continue
                product = Product.objects.create(
                    seller=seller,
                    category=category,
                    name=name,
                    description=description,
                    price=price_tzs,
                    condition=Product.Condition.LIKE_NEW,
                    quantity=1,
                    location="Dar es Salaam",
                    status=Product.Status.ACTIVE,
                )
                seed = sum(ord(c) for c in name)
                blob = _make_image(seed)
                product_image = ProductImage(product=product, is_primary=True, order=0)
                product_image.image.save(
                    f"{product.pk}.jpg",
                    ImageFile(blob),
                    save=True,
                )
                created_products += 1
                self.stdout.write(f"  + {product.name} — TZS {price_tzs:,} [{category.name}]")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created_categories} categories, {created_products} products created."
            )
        )
        active = Product.objects.filter(status=Product.Status.ACTIVE).count()
        self.stdout.write(f"Api: {active} active products total.")
