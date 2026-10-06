from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, Product, Cart, CartItem, Order

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


class Base(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='Analog')
        self.p = Product.objects.create(
            name='Casio A', brand='Casio', category=self.cat,
            price='1000.00', description='d', stock=3,
        )
        self.p2 = Product.objects.create(
            name='Fossil B', brand='Fossil', category=self.cat,
            price='2000.00', description='d', stock=1,
        )
        self.user = User.objects.create_user('bob', 'bob@example.com', 'S3cure-Pass!9')

    def login(self):
        self.client.login(username='bob', password='S3cure-Pass!9')


class SettingsTests(TestCase):
    def test_email_settings_present(self):
        self.assertEqual(settings.EMAIL_HOST, 'smtp.gmail.com')
        self.assertEqual(settings.EMAIL_PORT, 587)
        self.assertTrue(settings.EMAIL_USE_TLS)
        self.assertFalse(settings.EMAIL_USE_SSL)

    def test_no_hardcoded_password(self):
        src = open(settings.BASE_DIR / 'mypro' / 'settings.py').read()
        self.assertNotIn('pbpz', src)


class PageTests(Base):
    def test_product_detail_renders(self):
        r = self.client.get(reverse('product_detail', args=[self.p.id]))
        self.assertEqual(r.status_code, 200)

    def test_public_pages(self):
        for name in ['home', 'watches', 'brands', 'offers', 'contacts', 'login', 'register']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_brand_filter(self):
        r = self.client.get(reverse('watches') + '?brand=casio')
        self.assertEqual([p.name for p in r.context['products']], ['Casio A'])

    def test_bad_category_does_not_crash(self):
        r = self.client.get(reverse('watches') + '?category=abc')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context['products']), 2)


class CartTests(Base):
    def test_add_requires_post_and_login(self):
        url = reverse('add_to_cart', args=[self.p.id])
        self.assertEqual(self.client.post(url).status_code, 302)  # to login
        self.assertEqual(CartItem.objects.count(), 0)
        self.login()
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertEqual(CartItem.objects.get().quantity, 1)

    def test_cannot_exceed_stock(self):
        self.login()
        url = reverse('add_to_cart', args=[self.p2.id])  # stock 1
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(CartItem.objects.get().quantity, 1)

    def test_remove_is_post_only(self):
        self.login()
        self.client.post(reverse('add_to_cart', args=[self.p.id]))
        item = CartItem.objects.get()
        url = reverse('remove_from_cart', args=[item.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_checkout_without_cart_redirects(self):
        self.login()
        r = self.client.get(reverse('checkout'))
        self.assertRedirects(r, reverse('cart'))


@override_settings(EMAIL_BACKEND=LOCMEM)
class CheckoutTests(Base):
    def _fill_cart(self, qty=2):
        self.login()
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.p, quantity=qty)

    def test_order_created_stock_reduced_email_sent(self):
        self._fill_cart(2)
        r = self.client.post(reverse('checkout'), {'address': 'Street 1', 'phone': '9876543210'})
        self.assertRedirects(r, reverse('my_orders'))
        order = Order.objects.get()
        self.assertEqual(str(order.total_amount), '2000.00')
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 1)
        self.assertEqual(CartItem.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 1)
        page = self.client.get(reverse('my_orders'))
        self.assertContains(page, 'Order #%d' % order.id)

    def test_insufficient_stock_blocks_order(self):
        self._fill_cart(2)
        Product.objects.filter(pk=self.p.pk).update(stock=1)
        self.client.post(reverse('checkout'), {'address': 'Street 1', 'phone': '9876543210'})
        self.assertEqual(Order.objects.count(), 0)
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 1)

    def test_invalid_phone_rejected(self):
        self._fill_cart(1)
        r = self.client.post(reverse('checkout'), {'address': 'x', 'phone': 'abc'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_my_orders_empty_ok(self):
        self.login()
        self.assertEqual(self.client.get(reverse('my_orders')).status_code, 200)


class AuthTests(Base):
    def test_register_password_mismatch_message_shown(self):
        r = self.client.post(reverse('register'), {
            'username': 'new', 'email': 'n@example.com',
            'password': 'S3cure-Pass!9', 'confirm_password': 'different'})
        self.assertContains(r, 'Passwords do not match')
        self.assertFalse(User.objects.filter(username='new').exists())

    def test_register_weak_password_rejected(self):
        r = self.client.post(reverse('register'), {
            'username': 'new', 'email': 'n@example.com',
            'password': '12345678', 'confirm_password': '12345678'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username='new').exists())

    def test_register_duplicate_email_rejected(self):
        r = self.client.post(reverse('register'), {
            'username': 'new', 'email': 'BOB@example.com',
            'password': 'S3cure-Pass!9', 'confirm_password': 'S3cure-Pass!9'})
        self.assertContains(r, 'already exists')

    def test_register_ok(self):
        self.client.post(reverse('register'), {
            'username': 'new', 'email': 'n@example.com',
            'password': 'S3cure-Pass!9', 'confirm_password': 'S3cure-Pass!9'})
        self.assertTrue(User.objects.filter(username='new').exists())

    def test_login_next_redirect_and_open_redirect_blocked(self):
        r = self.client.post(reverse('login'), {
            'username': 'bob', 'password': 'S3cure-Pass!9', 'next': '/cart/'})
        self.assertRedirects(r, '/cart/', fetch_redirect_response=False)
        self.client.logout()
        r = self.client.post(reverse('login'), {
            'username': 'bob', 'password': 'S3cure-Pass!9', 'next': 'https://evil.com/'})
        self.assertRedirects(r, reverse('home'), fetch_redirect_response=False)

    def test_logout_post_only(self):
        self.login()
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.client.post(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)


@override_settings(EMAIL_BACKEND=LOCMEM, CONTACT_RECIPIENT='shop@example.com')
class ContactTests(TestCase):
    def test_contact_sends_email(self):
        r = self.client.post(reverse('contacts'), {
            'name': 'Asha', 'email': 'asha@example.com',
            'phone': '9876543210', 'message': 'Hello there'})
        self.assertRedirects(r, reverse('contacts'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['shop@example.com'])
        self.assertEqual(mail.outbox[0].reply_to, ['asha@example.com'])

    def test_contact_invalid_keeps_values(self):
        r = self.client.post(reverse('contacts'), {
            'name': 'Asha', 'email': 'not-an-email', 'message': 'Hi'})
        self.assertContains(r, 'Asha')
        self.assertEqual(len(mail.outbox), 0)


class ModelSafetyTests(Base):
    def test_category_with_products_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.cat.delete()
