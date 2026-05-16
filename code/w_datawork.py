import pandas as pd
import matplotlib.pyplot as plt
from adjustText import adjust_text

PATH: str = 'C:\\Users\\Вадимъ\\Documents\\GitHub\\CoffeePlusPlus\\'

class ProductAnalyzer:
    def __init__(self, df, product_name, unit, path=''):
        """
        df: DataFrame с колонками [Товар, Поставщик, Цена, Количество, Единица, Цена за кг/л]
        product_name: название товара (например, "Молоко")
        unit: единица измерения ("л" или "кг")
        path: путь для сохранения графиков
        """
        self.df = df.copy()
        self.product_name = product_name
        self.unit = unit
        self.path = path
        self.filtered_df = None
        self.aggregated_df = None
        
    def _swap_columns(self):
        """Меняет местами Товар и Поставщик, если Товар не равен product_name"""
        mask = self.df['Товар'] != self.product_name
        self.df.loc[mask, ['Товар', 'Поставщик']] = self.df.loc[mask, ['Поставщик', 'Товар']].values
    
    def _aggregate_by_supplier(self):
        """Группирует по поставщику, оставляет запись с минимальной ценой и добавляет рейтинг"""
        self.aggregated_df = self.df.loc[self.df.groupby('Поставщик')['Цена за кг/л'].idxmin()].copy()
        self.aggregated_df['Рейтинг'] = self.df.groupby('Поставщик')['Рейтинг'].transform('mean').round(1)
        self.aggregated_df = self.aggregated_df.sort_values('Цена за кг/л').reset_index(drop=True)
    
    def _calculate_score(self, rating_weight=0.7):
        """Рассчитывает скор на основе цены и рейтинга"""
        df = self.aggregated_df
        
        # Нормализация цены (инверсия: чем ниже цена, тем выше скор)
        price_min, price_max = df['Цена за кг/л'].min(), df['Цена за кг/л'].max()

        if price_max != price_min:
            df['цена_норм'] = 1 - (df['Цена за кг/л'] - price_min) / (price_max - price_min)

        else:
            df['цена_норм'] = 1
            
        # Нормализация рейтинга
        rating_min, rating_max = df['Рейтинг'].min(), df['Рейтинг'].max()

        if rating_max != rating_min:
            df['рейтинг_норм'] = (df['Рейтинг'] - rating_min) / (rating_max - rating_min)

        else:
            df['рейтинг_норм'] = 1
            
        # Скоринг
        df['Скор'] = (df['рейтинг_норм'] * rating_weight + 
                      df['цена_норм'] * (1 - rating_weight)).round(3)
        
        self.aggregated_df = df.sort_values('Скор', ascending=False).reset_index(drop=True)
    
    def _plot_scatter(self):
        """Точечная диаграмма: цена vs рейтинг"""
        df = self.aggregated_df
        
        fig, ax = plt.subplots(figsize=(14, 8))
        
        ax.scatter(df['Цена за кг/л'], df['Рейтинг'],
                   s=100, alpha=0.7, c='steelblue', edgecolors='white', linewidth=1.5)
        
        offsets = [(5, 5), (-10, 5), (5, -10), (-10, -10), (10, -5), (-5, 10)]
        for i, (_, row) in enumerate(df.iterrows()):
            offset = offsets[i % len(offsets)]
            ax.annotate(str(i+1), (row['Цена за кг/л'], row['Рейтинг']),
                       fontsize=9, fontweight='bold', xytext=offset, textcoords='offset points')
        
        ax.set_xlabel(f'Цена за {self.unit} (руб.)', fontsize=10)
        ax.set_ylabel('Рейтинг (средний по товарам поставщика)', fontsize=10)
        ax.set_title(f'{self.product_name}: анализ поставщиков (цена vs рейтинг)', fontsize=12)
        
        table_data = [[f"{i+1}. {row['Поставщик']}"] for i, (_, row) in enumerate(df.iterrows())]
        table = ax.table(cellText=table_data, loc='right', bbox=[1.15, 0, 0.3, 1])
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        
        plt.tight_layout()
        
        if self.path:
            plt.savefig(f"{self.path}{self.product_name}Scatter.png", dpi=150, bbox_inches='tight')

        plt.show()
    
    def _plot_score_bars(self):
        """Столбчатая диаграмма со скором"""
        df = self.aggregated_df
        
        fig, ax = plt.subplots(figsize=(14, 8))
        
        colors = plt.cm.RdYlGn(df['Скор'] / df['Скор'].max())
        bars = ax.barh(range(len(df)), df['Скор'], color=colors)
        
        ax.set_yticks(range(len(df)))
        ax.set_yticklabels(df['Поставщик'], fontsize=9)
        ax.set_xlabel('Скор', fontsize=10)
        ax.set_ylabel('Поставщик', fontsize=10)
        ax.set_title(f'{self.product_name}: рейтинг поставщиков', fontsize=12)
        ax.invert_yaxis()
        
        # Добавляем значения на бары
        for i, (_, row) in enumerate(df.iterrows()):
            ax.text(row['Скор'] + 0.01, i, f"{row['Скор']:.3f}", va='center', fontsize=8)
        
        plt.tight_layout()
        
        if self.path:
            plt.savefig(f"{self.path}{self.product_name}Score.png", dpi=150, bbox_inches='tight')

        plt.show()
    
    def run(self, rating_weight=0.7):
        """Запускает полный анализ"""
        self._swap_columns()
        self._aggregate_by_supplier()
        self._calculate_score(rating_weight)
        self._plot_scatter()
        self._plot_score_bars()
        return self.aggregated_df

milk: pd.DataFrame = pd.read_csv(PATH + "input\\milk.csv")
milk_analyzer = ProductAnalyzer(milk, 'Молоко', 'л', PATH + "output\\")
result_milk = milk_analyzer.run(rating_weight=0.7)