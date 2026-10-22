import io
import logging
from decimal import Decimal
from PIL import Image, ImageOps
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction, IntegrityError
from django.forms import inlineformset_factory
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.text import slugify
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .models import Product, Package, PackageItem
from .media import add_image

logger = logging.getLogger(__name__)

SLOT_CHOICES = [
    (1, 'Slot 1 (Left Promo Banner)'),
    (2, 'Slot 2 (Center Promo Banner)'),
    (3, 'Slot 3 (Right Promo Banner)'),
]


class PackageForm(forms.ModelForm):
    slot = forms.TypedChoiceField(
        choices=SLOT_CHOICES,
        coerce=int,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Choose slot 1, 2, or 3 for the promotional banner position.'
    )

    subtitle = forms.CharField(
        max_length=80,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Only This Week'}),
        help_text='Card subtitle displayed above the title.'
    )
    tagline = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Special promotional discount'}),
        help_text='Promotional tagline displayed on the card.'
    )

    class Meta:
        model = Package
        fields = ['slot', 'subtitle', 'tagline', 'discount_type', 'discount_value']

    def clean_subtitle(self):
        val = (self.cleaned_data.get('subtitle') or '').strip()
        return val or 'Only This Week'

    def clean_slot(self):
        slot = self.cleaned_data.get('slot')
        if slot not in (1, 2, 3):
            raise forms.ValidationError('Please choose banner slot 1, 2, or 3.')
        existing = Package.objects.filter(slot=slot)
        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            pkg_name = existing.first().product.name
            raise forms.ValidationError(
                f'Banner slot {slot} is already in use by "{pkg_name}". Please choose another slot or edit that package.'
            )
        return slot


class ItemForm(forms.ModelForm):
    class Meta:
        model = PackageItem
        fields = ['product', 'quantity']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_package=False, is_archived=False).order_by('name')
        self.fields['quantity'].max_value = 10000
        self.fields['quantity'].min_value = 1


class ProductForm(forms.ModelForm):
    banner = forms.ImageField(
        required=False,
        help_text='Promotional artwork automatically cropped to 867 × 441 px.'
    )

    class Meta:
        model = Product
        fields = ['name', 'slug', 'category', 'description', 'is_published', 'is_active']

    def clean_slug(self):
        slug = (self.cleaned_data.get('slug') or '').strip().lower()
        if not slug:
            name = self.cleaned_data.get('name') or ''
            slug = slugify(name)
        if not slug:
            raise forms.ValidationError('Please provide a product slug for this package.')
        existing = Product.objects.filter(slug=slug)
        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError(f'The slug "{slug}" is already used by another product or package.')
        return slug


Items = inlineformset_factory(
    Package, PackageItem, form=ItemForm, extra=4, can_delete=True,
    min_num=1, validate_min=True, max_num=50, validate_max=True
)


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'POST'])
def manage(request, pk=None):
    if not (request.user.is_staff or request.user.has_perm('catalog.view_package')):
        raise PermissionDenied

    package = get_object_or_404(Package, pk=pk) if pk else Package()
    product = package.product if pk else Product(is_package=True, regular_price=Decimal('1.00'), stock_confirmed=True)
    form = PackageForm(request.POST or None, instance=package)
    product_form = ProductForm(request.POST or None, request.FILES or None, instance=product, prefix='product')
    items = Items(request.POST or None, instance=package, prefix='items')

    if request.method == 'POST':
        if not (request.user.is_staff or request.user.has_perm('catalog.change_package' if pk else 'catalog.add_package')):
            raise PermissionDenied

        valid = form.is_valid() & product_form.is_valid() & items.is_valid()
        if valid:
            try:
                with transaction.atomic():
                    # 1. Lock existing product row on edit
                    if pk and product.pk:
                        Product.objects.select_for_update().get(pk=product.pk)

                    # 2. Extract selected valid product items
                    selected = [
                        f.cleaned_data for f in items.forms
                        if f.cleaned_data and f.cleaned_data.get('product') and not f.cleaned_data.get('DELETE')
                    ]
                    if not selected:
                        raise ValidationError('Please select at least one component product with a valid quantity.')

                    # 3. Calculate bundle total base price
                    base = sum(row['product'].price * row['quantity'] for row in selected)
                    if base <= Decimal('0'):
                        raise ValidationError('Selected products must have a combined price greater than £0.00.')

                    package = form.save(commit=False)
                    if package.discount_type == 'amount' and package.discount_value > base:
                        raise ValidationError(
                            f'Discount amount (£{package.discount_value}) cannot exceed the bundle price (£{base}).'
                        )
                    if package.discount_value < Decimal('0'):
                        raise ValidationError('Discount value cannot be negative.')
                    if package.discount_type == 'percent' and package.discount_value > Decimal('100'):
                        raise ValidationError('Discount percentage cannot exceed 100%.')

                    # 4. Save product
                    product = product_form.save(commit=False)
                    product.is_package = True
                    product.stock_confirmed = True
                    product.regular_price = base
                    discounted = (
                        base * (100 - package.discount_value) / 100
                        if package.discount_type == 'percent'
                        else base - package.discount_value
                    ).quantize(Decimal('.01'))
                    product.sale_price = discounted if 0 < discounted < base else None

                    # Check image requirement if published
                    upload = request.FILES.get('product-banner')
                    if product.is_published and not upload and (not product.pk or not product.main_image):
                        raise ValidationError('Upload a banner image before publishing the package.')

                    product.save()

                    # 5. Save package and item relationships
                    package.product = product
                    package.save()
                    items.instance = package
                    items.save()

                    # 6. Process and attach banner artwork if uploaded
                    if upload:
                        try:
                            raw = upload.read()
                            with Image.open(io.BytesIO(raw)) as image:
                                cropped = ImageOps.fit(
                                    ImageOps.exif_transpose(image).convert('RGB'),
                                    (867, 441),
                                    method=Image.Resampling.LANCZOS
                                )
                                output = io.BytesIO()
                                cropped.save(output, format='JPEG', quality=92)

                            # Clear previous images on the package to avoid 5-image limit
                            product.images.all().delete()
                            banner_file = ContentFile(output.getvalue(), name=f'{product.slug}-banner.jpg')
                            add_image(product.pk, banner_file, main=True, alt=product.name)
                        except Exception as img_exc:
                            raise ValidationError(f'Failed to process uploaded banner image: {img_exc}') from img_exc

                    # Re-save to trigger catalog revision increment and cache invalidation
                    product.save()

                messages.success(request, f'Package "{product.name}" saved successfully and placed in slot {package.slot}.')
                return redirect('package-edit', pk=package.pk)
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages) if hasattr(exc, 'messages') else str(exc))
            except IntegrityError as exc:
                logger.warning('Package save integrity error: %s', exc)
                messages.error(request, 'This slot number or product slug is already in use. Please select a different slot or slug.')
            except Exception as exc:
                logger.exception('Unexpected error saving product package')
                messages.error(request, f'An error occurred while saving the package: {exc}')
        else:
            messages.error(request, 'Please resolve the errors highlighted below.')

    return render(request, 'catalog/package_form.html', {
        'form': form,
        'product_form': product_form,
        'items': items,
        'packages': Package.objects.select_related('product').order_by('slot'),
        'package': package,
        'active_page': 'packages'
    })
