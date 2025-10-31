from django.shortcuts import render, redirect, get_object_or_404
from .models import Category,Book
from django.db.models import Sum
from django import forms
import pandas as pd
from decimal import Decimal,InvalidOperation
from django.db import transaction
from django.contrib import messages

# ---- Formulaire ----
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']

# ---- CRUD Views ----

# Lister toutes les catégories
def category_list(request):
    categories = Category.objects.all()
    return render(request, 'books/category_list.html', {'categories': categories})


# Créer une catégorie
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('category_list')
    else:
        form = CategoryForm()
    return render(request, 'books/category_form.html', {'form': form})


# Modifier une catégorie
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect('category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'books/category_form.html', {'form': form})


# Supprimer une catégorie
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        return redirect('category_list')
    return render(request, 'books/category_confirm_delete.html', {'category': category})


# ---- Formulaire pour Book ----
class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'subtitle', 'authors', 'publisher', 'published_date', 'category', 'distribution_expense']
        widgets = {
            'published_date': forms.DateInput(attrs={'type': 'date'})
        }

# ---- CRUD Views ----

# Lister tous les livres
def book_list(request):
    books = Book.objects.select_related('category').all()
    return render(request, 'books/book_list.html', {'books': books})


# Créer un livre
def book_create(request):
    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('book_list')
    else:
        form = BookForm()
    return render(request, 'books/book_form.html', {'form': form})


# Modifier un livre
def book_update(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            return redirect('book_list')
    else:
        form = BookForm(instance=book)
    return render(request, 'books/book_form.html', {'form': form})


# Supprimer un livre
def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        book.delete()
        return redirect('book_list')
    return render(request, 'books/book_confirm_delete.html', {'book': book})


# Formulaire simple d'upload
class UploadFileForm(forms.Form):
    file = forms.FileField(label="Fichier Excel (.xlsx)",
                            widget=forms.FileInput(attrs={
            'class': 'absolute inset-0 w-full h-full opacity-0 cursor-pointer',
            'accept': '.xlsx,.xls'
        }))


def book_import(request):
    """
    Vue pour importer un fichier Excel et créer des objets Book (et Category si manquant).
    """
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['file']

            try:
                # Lire le fichier Excel dans un DataFrame pandas
                df = pd.read_excel(excel_file)

                # Vérifier colonnes requises
                required = {'title', 'subtitle', 'authors', 'publisher', 'published_date', 'category', 'distribution_expense'}
                missing = required - set(df.columns.str.lower())
                # pandas peut produire noms avec casse: on normalise
                # Re-normalisation: renommer les colonnes pour lower()
                df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

                missing = required - set(df.columns)
                if missing:
                    messages.error(request, f"Colonnes manquantes dans l'Excel : {', '.join(missing)}")
                    return redirect('book_import')

                # Nettoyage et conversion
                # Supprimer lignes vides (titre vide)
                df = df[df['title'].notna()]

                # Convertir published_date en datetime (pandas)
                df['published_date'] = pd.to_datetime(df['published_date'], errors='coerce', dayfirst=True)

                # S’assurer que distribution_expense est numérique et sans NaN
                df['distribution_expense'] = pd.to_numeric(df['distribution_expense'], errors='coerce')

                # Trouver les lignes invalides
                invalid_dates = df['published_date'].isna()
                invalid_costs = df['distribution_expense'].isna()

                if invalid_dates.any() or invalid_costs.any():
                    bad_rows = df[invalid_dates | invalid_costs]
                    print("🚨 Lignes invalides détectées :")
                    print(bad_rows)  # affichera dans ton terminal Django
                    messages.error(request,
                        f"{len(bad_rows)} ligne(s) ont des dates ou coûts invalides. Vérifie ton fichier.")
                    return redirect('book_import')


                # Préparer la création en base
                books_to_create = []
                categories_cache = {}  # nom -> Category

                # Récupérer toutes les catégories existantes en une requête (optim)
                existing_categories = Category.objects.all()
                for c in existing_categories:
                    categories_cache[c.name.lower()] = c

                # Transaction pour création atomique
                with transaction.atomic():
                    for _, row in df.iterrows():
                        cat_name = str(row['category']).strip()
                        cat_key = cat_name.lower()

                        if cat_key in categories_cache:
                            cat = categories_cache[cat_key]
                        else:
                            cat = Category.objects.create(name=cat_name)
                            categories_cache[cat_key] = cat

                        try:
                            cost = Decimal(row['distribution_expense'])
                        except (InvalidOperation, TypeError):
                            cost = Decimal(0)

                        # Gestion sûre des champs facultatifs
                        subtitle = str(row['subtitle']).strip() if not pd.isna(row['subtitle']) else ""
                        authors = str(row['authors']).strip() if not pd.isna(row['authors']) else ""
                        publisher = str(row['publisher']).strip() if not pd.isna(row['publisher']) else ""

                        # Gestion de la date
                        pub_date = None
                        if not pd.isna(row['published_date']):
                            try:
                                pub_date = row['published_date'].date()
                            except AttributeError:
                                pub_date = None

                            book = Book(
                                title=str(row['title']).strip(),
                                subtitle=subtitle,
                                authors=authors,
                                publisher=publisher,
                                published_date=pub_date,
                                category=cat,
                                distribution_expense=cost
                            )
                            books_to_create.append(book)

                        # Bulk create pour efficacité
                    Book.objects.bulk_create(books_to_create)

                    messages.success(request, f"Import terminé : {len(books_to_create)} livres ajoutés.")
                    return redirect('book_list')

            except Exception as e:
                # Logue l'erreur selon ton setup; ici on renvoie un message
                messages.error(request, f"Erreur durant l'import : {str(e)}")
                return redirect('book_import')
    else:
        form = UploadFileForm()

    return render(request, 'books/book_import.html', {'form': form})


# Vue des rapports 
def report_view(request):
    # Agrégation par catégorie
    report_data = (
        Book.objects
        .values('category__name')
        .annotate(total_expense=Sum('distribution_expense'))
        .order_by('-total_expense')
    )

    # Préparer les données pour Chart.js
    categories = [item['category__name'] for item in report_data]
    expenses = [float(item['total_expense']) for item in report_data]

    total_global = sum(expenses) if expenses else 0
    average_expense = total_global / len(expenses) if expenses else 0
    
    # Catégorie la plus coûteuse
    max_category = report_data.first() if report_data else None

    # Couleurs pour les indicateurs
    chart_colors = [
        '#4f46e5', '#6366f1', '#8b5cf6', '#a855f7', 
        '#d946ef', '#ec4899', '#f97316', '#f59e0b'
    ]

    return render(request, 'books/report.html', {
        'report_data': report_data,
        'categories': categories,
        'expenses': expenses,
        'total_global': total_global,
        'average_expense': average_expense,
        'max_category': max_category,
        'chart_colors': chart_colors,
    })