from django.urls import path
from . import views


urlpatterns = [

    # HOME
    path(
        '',
        views.home,
        name='home'
    ),

    # WATCHES
    path(
        'watches/',
        views.watches,
        name='watches'
    ),

    # PRODUCT
    path(
        'product/<int:product_id>/',
        views.product_detail,
        name='product_detail'
    ),

    # CART
    path(
        'cart/',
        views.cart,
        name='cart'
    ),

    path(
        'cart/add/<int:product_id>/',
        views.add_to_cart,
        name='add_to_cart'
    ),

    path(
        'cart/remove/<int:item_id>/',
        views.remove_from_cart,
        name='remove_from_cart'
    ),

    # CHECKOUT
    path(
        'checkout/',
        views.checkout,
        name='checkout'
    ),

    # ORDERS
    path(
        'my-orders/',
        views.my_orders,
        name='my_orders'
    ),

    # LOGIN
    path(
        'login/',
        views.login_view,
        name='login'
    ),

    # REGISTER
    path(
        'register/',
        views.register,
        name='register'
    ),

    # LOGOUT
    path(
        'logout/',
        views.logout_view,
        name='logout'
    ),

    # OTHER PAGES
    path(
        'brands/',
        views.brands,
        name='brands'
    ),

    path(
        'offers/',
        views.offers,
        name='offers'
    ),

    path(
        'contact/',
        views.contacts,
        name='contacts'
    ),
]