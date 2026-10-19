from django.contrib.admin.forms import AdminAuthenticationForm


class AdminLoginForm(AdminAuthenticationForm):
    """Django authentication with active/staff checks and accessible controls."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "placeholder": "Enter your username", "autocomplete": "username",
            "autofocus": True,
        })
        self.fields["password"].widget.attrs.update({
            "placeholder": "Enter your password", "autocomplete": "current-password",
        })
