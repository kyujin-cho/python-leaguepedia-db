# python-leaguepedia-db

Python DB-API Adaptor for Leaguepedia

## Installation

```python
pip install python-leaguepedia-db
```

## Usage

```python
>>> import leaguepediadb
>>> connection = leaguepediadb.connect()
>>> cursor = connection.cursor()
>>> cursor.execute(
...     'SELECT SP.Team AS Team, SP.Role AS Role, SP.Link AS Link '
...     'FROM ScoreboardPlayers SP '
...     'WHERE SP.OverviewPage = ? '
...     'GROUP BY SP.Link '
...     'ORDER BY SP.DateTime_UTC DESC',
...     ('LCK/2022 Season/Spring Season',)
... )
```

```python
>>> cursor.fetchone()  # {'Team': 'DRX', 'Role': 'Bot', 'Link': 'Taeyoon'}
```

```python
>>> for row in cursor.fetchall():
...     print(row)
...
# {'Team': 'Fredit BRION', 'Role': 'Bot', 'Link': 'Gamin'}
# {'Team': 'Fredit BRION', 'Role': 'Top', 'Link': 'Soboro'}
# {'Team': 'Fredit BRION', 'Role': 'Mid', 'Link': 'Feisty'}
# {'Team': 'Fredit BRION', 'Role': 'Support', 'Link': 'Loopy'}
...
```
