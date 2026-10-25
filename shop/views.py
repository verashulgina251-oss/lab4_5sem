from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Category, Product, Order, OrderItem


# ---------- Главная ----------
def shop_index(request):
    categories = Category.objects.all()
    products = Product.objects.filter(available=True)
    context = {
        'categories': categories,
        'products': products,
        'cart_count': _cart_count(request),
    }
    return render(request, 'shop/index.html', context)


# ---------- Карточка товара ----------
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, available=True)
    related_products = Product.objects.filter(
        category=product.category, available=True
    ).exclude(id=product.id)[:5]
    context = {
        'product': product,
        'related_products': related_products,
        'cart_count': _cart_count(request),
    }
    return render(request, 'shop/product.html', context)


# ---------- Корзина ----------
def _get_cart(request):
    return request.session.get('cart', {})


def _save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True


def _cart_count(request):
    return sum(_get_cart(request).values())


def _cart_items_and_total(request):
    cart = _get_cart(request)
    items = []
    total = 0
    if cart:
        products = Product.objects.filter(id__in=[int(pid) for pid in cart.keys()])
        for product in products:
            qty = int(cart[str(product.id)])
            subtotal = product.price * qty
            total += subtotal
            items.append({
                'product': product,
                'quantity': qty,
                'subtotal': subtotal,
            })
    return items, total


def cart_view(request):
    items, total = _cart_items_and_total(request)
    return render(request, 'shop/cart.html', {
        'cart_items': items,
        'cart_total': total,
        'cart_count': _cart_count(request),
    })


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, available=True)
    cart = _get_cart(request)
    pid = str(product.id)
    cart[pid] = cart.get(pid, 0) + 1
    _save_cart(request, cart)
    return redirect('shop:cart')


@require_POST
def remove_from_cart(request, product_id):
    cart = _get_cart(request)
    pid = str(product_id)
    if pid in cart:
        del cart[pid]
    _save_cart(request, cart)
    return redirect('shop:cart')


@require_POST
def update_cart(request, product_id):
    cart = _get_cart(request)
    pid = str(product_id)
    try:
        qty = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        qty = 1
    if qty > 0:
        cart[pid] = qty
    else:
        cart.pop(pid, None)
    _save_cart(request, cart)
    return redirect('shop:cart')


# ---------- Оформление заказа ----------
def checkout_view(request):
    items, total = _cart_items_and_total(request)

    if request.method == 'POST':
        if not items:
            return redirect('shop:cart')

        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            first_name=request.POST.get('first_name', '').strip(),
            last_name=request.POST.get('last_name', '').strip(),
            phone=request.POST.get('phone', '').strip(),
            address=request.POST.get('address', '').strip(),
            paid=False,
        )

        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                price=item['product'].price,
                quantity=item['quantity'],
            )

        request.session['cart'] = {}
        request.session.modified = True

        messages.success(request, f'Заказ #{order.id} успешно оформлен!')
        return redirect('shop:index')

    return render(request, 'shop/checkout.html', {
        'cart_items': items,
        'cart_total': total,
        'cart_count': _cart_count(request),
    })


# ---------- Аутентификация ----------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('shop:account')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}!')
            return redirect('shop:account')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль.')

    return render(request, 'shop/account-login.html', {
        'cart_count': _cart_count(request),
    })


def register_view(request):
    if request.user.is_authenticated:
        return redirect('shop:account')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        if not username or not password:
            messages.error(request, 'Имя пользователя и пароль обязательны.')
        elif password != password2:
            messages.error(request, 'Пароли не совпадают.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Такое имя пользователя уже занято.')
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)
            messages.success(request, f'Аккаунт {user.username} создан!')
            return redirect('shop:account')

    return render(request, 'shop/account-login.html', {
        'cart_count': _cart_count(request),
    })


def logout_view(request):
    logout(request)
    messages.info(request, 'Вы вышли из аккаунта.')
    return redirect('shop:index')


# ---------- Личный кабинет ----------
def account_view(request):
    if not request.user.is_authenticated:
        return redirect('shop:login')

    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'shop/account-orders.html', {
        'orders': orders,
        'cart_count': _cart_count(request),
    })