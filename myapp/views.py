import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import EmailMessage, send_mail
from django.db import transaction
from django.db.models import F
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import RegisterForm, CheckoutForm, ContactForm
from .models import (
    Product,
    Category,
    Cart,
    CartItem,
    Order,
    OrderItem,
)

logger = logging.getLogger(__name__)


# =========================
# HOME
# =========================

def home(request):
    products = Product.objects.all().order_by('-created_at')[:6]
    categories = Category.objects.all()

    return render(request, 'home.html', {
        'products': products,
        'categories': categories,
    })


# =========================
# WATCHES
# =========================

def watches(request):
    products = Product.objects.select_related('category')
    categories = Category.objects.all()

    category_id = request.GET.get('category', '').strip()
    brand = request.GET.get('brand', '').strip()

    # Ignore non-numeric values instead of crashing with a 500 error
    if category_id.isdigit():
        products = products.filter(category_id=int(category_id))

    if brand:
        products = products.filter(brand__iexact=brand)

    return render(request, 'watches.html', {
        'products': products,
        'categories': categories,
        'selected_category': category_id,
        'selected_brand': brand,
    })


# =========================
# PRODUCT DETAILS
# =========================

def product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related('category'),
        id=product_id
    )

    return render(request, 'product_detail.html', {
        'product': product,
    })


# =========================
# ADD TO CART  (POST only)
# =========================

@login_required
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if product.stock < 1:
        messages.error(request, f"{product.name} is out of stock.")
        return redirect('product_detail', product_id=product.id)

    cart, _ = Cart.objects.get_or_create(user=request.user)

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product
    )

    if not created:
        if item.quantity >= product.stock:
            messages.warning(
                request,
                f"Only {product.stock} unit(s) of {product.name} available."
            )
            return redirect('cart')

        item.quantity += 1
        item.save()

    messages.success(request, f"{product.name} added to cart!")

    if request.POST.get('buy_now'):
        return redirect('checkout')

    return redirect('cart')


# =========================
# CART
# =========================

@login_required
def cart(request):
    user_cart, _ = Cart.objects.get_or_create(user=request.user)

    items = CartItem.objects.filter(
        cart=user_cart
    ).select_related('product')

    total = sum(item.total_price() for item in items)

    return render(request, 'cart.html', {
        'items': items,
        'total': total,
    })


# =========================
# REMOVE FROM CART  (POST only)
# =========================

@login_required
@require_POST
def remove_from_cart(request, item_id):
    item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user
    )

    item.delete()

    messages.success(request, "Product removed from cart.")

    return redirect('cart')


# =========================
# CHECKOUT
# =========================

def _send_order_email(order):
    """Order confirmation. Never breaks checkout if mail fails."""
    email = order.user.email

    if not email:
        return

    lines = [
        f"Hi {order.user.username},",
        "",
        f"Thank you for your order #{order.id}.",
        "",
    ]
    for item in order.orderitem_set.select_related('product'):
        lines.append(
            f"- {item.product.name} x {item.quantity} = Rs.{item.total_price()}"
        )
    lines += [
        "",
        f"Total: Rs.{order.total_amount}",
        f"Delivery address: {order.address}",
        "",
        "TimeZone - Time That Defines You",
    ]

    try:
        send_mail(
            subject=f"TimeZone order #{order.id} confirmed",
            message="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )
    except Exception:
        logger.exception("Could not send confirmation e-mail for order %s", order.id)


@login_required
def checkout(request):
    user_cart, _ = Cart.objects.get_or_create(user=request.user)

    items = CartItem.objects.filter(
        cart=user_cart
    ).select_related('product')

    if not items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('cart')

    total = sum(item.total_price() for item in items)

    if request.method == 'POST':
        form = CheckoutForm(request.POST)

        if form.is_valid():
            order = None

            with transaction.atomic():
                # Lock + re-read products so stock can't go negative
                locked = {
                    p.id: p
                    for p in Product.objects.select_for_update().filter(
                        id__in=[i.product_id for i in items]
                    )
                }

                problem = None
                for item in items:
                    product = locked[item.product_id]
                    if item.quantity > product.stock:
                        problem = (
                            f"Not enough stock for {product.name} "
                            f"(only {product.stock} left)."
                        )
                        break

                if problem is None:
                    order = Order.objects.create(
                        user=request.user,
                        total_amount=total,
                        address=form.cleaned_data['address'],
                        phone=form.cleaned_data['phone']
                    )

                    for item in items:
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            quantity=item.quantity,
                            price=item.product.price
                        )
                        Product.objects.filter(
                            id=item.product_id
                        ).update(stock=F('stock') - item.quantity)

                    items.delete()

            if order is None:
                messages.error(request, problem)
                return redirect('cart')

            _send_order_email(order)

            messages.success(request, "Your order has been placed successfully!")
            return redirect('my_orders')
    else:
        form = CheckoutForm()

    return render(request, 'checkout.html', {
        'form': form,
        'items': items,
        'total': total,
    })


# =========================
# MY ORDERS
# =========================

@login_required
def my_orders(request):
    orders = Order.objects.filter(
        user=request.user
    ).prefetch_related('orderitem_set__product').order_by('-created_at')

    return render(request, 'my_orders.html', {
        'orders': orders,
    })


# =========================
# LOGIN
# =========================

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    next_url = request.POST.get('next') or request.GET.get('next', '')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            safe = url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            )
            if next_url and safe:
                return redirect(next_url)

            if user.is_staff:
                return redirect('/admin/')

            return redirect('home')

        messages.error(request, "Invalid username or password.")

    return render(request, 'login.html', {'next': next_url})

# =========================
# REGISTER
# =========================

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            # Send welcome email
            try:
                send_mail(
                    subject='Welcome to TimeZone',
                    message=(
                        f'Hello {username},\n\n'
                        'Welcome to TimeZone!\n\n'
                        'Your account has been successfully created. '
                        'You can now browse our watches, add products to your cart, '
                        'and place orders.\n\n'
                        'Thank you for joining TimeZone!\n\n'
                        'Regards,\n'
                        'TimeZone Team'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )

                messages.success(
                    request,
                    'Account created successfully! A welcome email has been sent.'
                )

            except Exception:
                messages.success(
                    request,
                    'Account created successfully! Welcome to TimeZone.'
                )

            login(request, user)

            return redirect('home')

    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})
# =========================
# LOGOUT  (POST only)
# =========================

@require_POST
def logout_view(request):
    logout(request)
    return redirect('home')


# =========================
# BRANDS
# =========================

def brands(request):
    return render(request, 'brands.html')


# =========================
# OFFERS
# =========================

def offers(request):
    return render(request, 'offers.html')


# =========================
# CONTACT
# =========================

def contacts(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data

            body = (
                f"Name: {data['name']}\n"
                f"Email: {data['email']}\n"
                f"Phone: {data['phone'] or '-'}\n\n"
                f"{data['message']}"
            )

            recipient = settings.CONTACT_RECIPIENT or settings.DEFAULT_FROM_EMAIL

            try:
                EmailMessage(
                    subject=f"TimeZone contact form: {data['name']}",
                    body=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient],
                    reply_to=[data['email']],
                ).send()
            except Exception:
                logger.exception("Contact form e-mail failed")
                messages.error(
                    request,
                    "Sorry, we couldn't send your message right now. "
                    "Please try again later."
                )
            else:
                messages.success(
                    request,
                    "Thank you! Your message has been sent."
                )
                return redirect('contacts')
    else:
        form = ContactForm()

    return render(request, 'contacts.html', {'form': form})
