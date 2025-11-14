import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load the dataset. 
dataframe_raw = pd.read_csv('books_original.csv')

def clear_data(dataframe):
    '''
    This function analyzes and clears the dataset by identifying and addressing missing values, anomalies, and inconsistencies in the data.
    It performs the following steps:
    1. Removes duplicate entries.
    1. Analyzes the dataset to identify missing values in each column.
    2. Identifies anomalies in numerical data columns by checking for outliers or unexpected values.
    3. Identifies anomalies in categorical data columns by checking for inconsistent naming conventions or unexpected categories.
    4. Cleans the data by:
       - Standardizing naming conventions in categorical columns.
       - Removing redundant columns.
       - Converting data formats to ensure consistency (e.g., date formats).
    5. Returns the cleaned dataset for further analysis.
    6. Visualizes data.
    
    '''

    dataframe = dataframe.copy()  # Work on a copy to avoid modifying original DataFrame

    # Analyze and prepare dataset for clearing
    print("Initial Data Overview:")
    dataframe.info()
    dataframe.describe()
    dataframe.head()

    # Remove duplicates
    dataframe = dataframe.drop_duplicates()

     # Check for missing values
    print("\nMissing Values in Each Column:")
    print(dataframe.isnull().sum())

    # Check for anomalies in numerical data columns
    print("\nAnomalies in Numerical Columns:")
    max_entries = dataframe.select_dtypes(include=[np.number]).max()
    min_entries = dataframe.select_dtypes(include=[np.number]).min()
    print("Max Values:\n", max_entries)
    print("Min Values:\n", min_entries)

    # Check for anomalies in categorical data columns
    print("\nAnomalies in Categorical Columns:")
    for col in dataframe.select_dtypes(include=['object']).columns:
        unique_values = dataframe[col].unique()
        print(f"Column '{col}' Unique Values:\n", unique_values)

    # Data clearing steps
    # 1. Dataset review has identified potential issues with missing values in average_rating, isbn, isbn13 and num_pages columns.
    numeric_cols = ['average_rating', 'isbn', 'isbn13', 'num_pages', 'ratings_count', 'text_reviews_count']

    for col in numeric_cols:
        dataframe[col] = pd.to_numeric(dataframe[col], errors='coerce')
    print(dataframe[dataframe[numeric_cols].isna()])
    

    # 2. Convert publication date to datetime format
    dataframe['publication_date'] = pd.to_datetime(dataframe['publication_date'], errors='coerce', dayfirst=False)
    print(dataframe[dataframe['publication_date'].isna()])

     # Handle missing values
    dataframe = dataframe.dropna(subset=['average_rating', 'isbn', 'isbn13', 'num_pages', 'publication_date'])

    print("\nAfter Handling Missing Values:")
    print(dataframe.isnull().sum())
    print(dataframe.dtypes)
    print(dataframe.head())

    return dataframe
# 6. Visualizations before and after cleaning
def visualize_data(dataframe, title_suffix=''):
     # Average rating distribution
    plt.figure(figsize=(10, 6))
    sns.histplot(dataframe['average_rating'], bins=30, kde=True, color='skyblue')
    plt.title(f'Average Rating Distribution {title_suffix}')
    plt.xlabel('Average Rating')
    plt.ylabel('Frequency')
    plt.show()

    # Number of pages distribution
    plt.figure(figsize=(10, 6))
    sns.histplot(dataframe['num_pages'], bins=30, kde=True, color='salmon')
    plt.title(f'Number of Pages Distribution {title_suffix}')
    plt.xlabel('Number of Pages')
    plt.ylabel('Frequency')
    plt.show()

    # Top 10 authors by book count
    top_authors = dataframe['authors'].value_counts().nlargest(10)
    plt.figure(figsize=(12,6))
    sns.barplot(x=top_authors.values, y=top_authors.index, palette='viridis')
    plt.title(f'Top 10 Authors by Number of Books {title_suffix}')
    plt.xlabel('Number of Books')
    plt.ylabel('Author')
    plt.show()

    # Books published per year
    dataframe['publication_year'] = dataframe['publication_date'].dt.year
    books_per_year = dataframe['publication_year'].value_counts().sort_index()
    plt.figure(figsize=(12,6))
    sns.lineplot(x=books_per_year.index, y=books_per_year.values, marker='o')
    plt.title(f'Number of Books Published per Year {title_suffix}')
    plt.xlabel('Year')
    plt.ylabel('Number of Books')
    plt.show()

# Clear the data
dataframe_cleaned = clear_data(dataframe_raw)
#write_path = 'cleaned_books_v2.csv'
#dataframe_cleaned.to_csv(write_path, index=False)

# Visualize cleaned data
visualize_data(dataframe_cleaned, title_suffix='(Cleaned)')