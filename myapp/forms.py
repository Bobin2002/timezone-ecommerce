import re

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


class RegisterForm(forms.ModelForm):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")

        return email

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")

        if password:
            # Applies the rules in AUTH_PASSWORD_VALIDATORS
            temp_user = User(
                username=cleaned_data.get('username', ''),
                email=cleaned_data.get('email', ''),
            )
            try:
                validate_password(password, temp_user)
            except ValidationError as error:
                self.add_error('password', error)

        return cleaned_data


phone_validator = RegexValidator(
    regex=r'^\+?[0-9 \-]{7,15}$',
    message="Enter a valid phone number (7-15 digits).",
)


class CheckoutForm(forms.Form):
    address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4})
    )
    phone = forms.CharField(
        max_length=15,
        validators=[phone_validator]
    )


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(
        max_length=15,
        required=False,
        validators=[phone_validator]
    )
    message = forms.CharField(
        max_length=3000,
        widget=forms.Textarea
    )

    def clean_name(self):
        # Prevent header injection through newlines in the name
        return re.sub(r'[\r\n]+', ' ', self.cleaned_data['name']).strip()
