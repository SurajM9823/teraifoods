import io
from decimal import Decimal
from PIL import Image, ImageOps
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction, IntegrityError
from django.forms import inlineformset_factory
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .models import Product, Package, PackageItem
from .media import prepare_image, add_image


class PackageForm(forms.ModelForm):
    class Meta:
        model=Package
        fields=['slot','subtitle','tagline','discount_type','discount_value']


class ItemForm(forms.ModelForm):
    class Meta:
        model=PackageItem
        fields=['product','quantity']

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['product'].queryset=Product.objects.filter(is_package=False,is_archived=False).order_by('name')
        self.fields['quantity'].max_value=10000


class ProductForm(forms.ModelForm):
    banner=forms.ImageField(required=False,help_text='Cropped to 867 × 441 pixels to match the existing cards.')

    class Meta:
        model=Product
        fields=['name','slug','category','description','is_published','is_active']


Items=inlineformset_factory(Package,PackageItem,form=ItemForm,extra=4,can_delete=True,min_num=1,validate_min=True,max_num=50,validate_max=True)


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET','POST'])
def manage(request,pk=None):
    if not request.user.has_perm('catalog.view_package'):
        raise PermissionDenied
    package=get_object_or_404(Package,pk=pk) if pk else Package()
    product=package.product if pk else Product(is_package=True,regular_price=Decimal('.01'),stock_confirmed=True)
    form=PackageForm(request.POST or None,instance=package)
    product_form=ProductForm(request.POST or None,request.FILES or None,instance=product,prefix='product')
    items=Items(request.POST or None,instance=package,prefix='items')
    if request.method=='POST':
        if not request.user.has_perm('catalog.change_package' if pk else 'catalog.add_package'):
            raise PermissionDenied
        valid=form.is_valid() & product_form.is_valid() & items.is_valid()
        if valid:
            try:
                with transaction.atomic():
                    # Lock the parent just as checkout does, before replacing its contents.
                    if pk: Product.objects.select_for_update().get(pk=product.pk)
                    product=product_form.save(commit=False);product.is_package=True;product.stock_confirmed=True
                    selected=[f.cleaned_data for f in items.forms if f.cleaned_data and not f.cleaned_data.get('DELETE')]
                    base=sum(row['product'].price*row['quantity'] for row in selected)
                    package=form.save(commit=False)
                    if package.discount_type=='amount' and package.discount_value>base:
                        raise ValidationError('Discount cannot exceed the package contents price.')
                    product.regular_price=base
                    discounted=(base*(100-package.discount_value)/100 if package.discount_type=='percent' else base-package.discount_value).quantize(Decimal('.01'))
                    product.sale_price=discounted if 0<discounted<base else None
                    if product.is_published and not request.FILES.get('product-banner') and (not product.pk or not product.main_image):
                        raise ValidationError('Upload a banner image before publishing.')
                    product.save();package.product=product;package.save();items.instance=package;items.save()
                    upload=request.FILES.get('product-banner')
                    if upload:
                        checked=prepare_image(upload)
                        with default_storage.open(checked['source'],'rb') as source:
                            with Image.open(source) as image:
                                crop=ImageOps.fit(image.convert('RGB'),(867,441),method=Image.Resampling.LANCZOS)
                                output=io.BytesIO();crop.save(output,format='JPEG',quality=92)
                        add_image(product.pk,ContentFile(output.getvalue(),name='package.jpg'),main=True,alt=product.name)
                    # Explicit save after components makes catalog cache invalidation run.
                    product.save()
                messages.success(request,'Package saved. Published packages appear in the selected homepage banner slot.')
                return redirect('package-edit',pk=package.pk)
            except (ValidationError,IntegrityError) as exc:
                messages.error(request,' '.join(exc.messages) if isinstance(exc,ValidationError) else 'This slot or product identifier is already in use.')
    return render(request,'catalog/package_form.html',{'form':form,'product_form':product_form,'items':items,
        'packages':Package.objects.select_related('product').order_by('slot'),'package':package,'active_page':'products'})
