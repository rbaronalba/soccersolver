"""Umbrales compartidos entre limpieza y algoritmo. Centralizados aqui para
que ajustar un rango no implique tocar varios ficheros a la vez."""

MIN_AGE, MAX_AGE = 14, 45
MIN_MARKET_VALUE, MAX_MARKET_VALUE = 1_000, 300_000_000
MIN_WAGE, MAX_WAGE = 1_000, 60_000_000  # sueldo anual

MIN_COMPARABLES = 8
MAX_AGE_WINDOW = 12
