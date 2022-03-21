from dataclasses import dataclass, field
import json
from typing import Any, Iterable, List, Mapping, Optional, Tuple, Union

import mwclient
import mo_sql_parsing


__all__ = (
    'ConnectionClosedError',
    'LeaguepediaQuery',
    'LeaguepediaConnection',
    'LeaguepediaCursor',
    'connect',
    'apilevel',
    'threadsafety',
)


apilevel = '2.0'
threadsafety = 0


class ConnectionClosedError(BaseException):
    pass


@dataclass
class LeaguepediaQuery:

    tables: List[str]
    fields: List[str]
    joins: Optional[List[str]] = field(default=None)
    where: Optional[str] = field(default=None)
    group_by: Optional[str] = field(default=None)
    order_by: List[Tuple[str, str]] = field(default_factory=lambda: [])
    limit: Optional[int] = field(default=500)
    offset: Optional[int] = field(default=0)
    having: Optional[str] = field(default=None)

    @classmethod
    def _compile_column(cls, node):
        if isinstance(node, str):
            return node
        ret = node['value']
        if 'name' in node:
            ret += '=' + node['name']
        return ret

    @classmethod
    def parse(cls, line: str):
        ret = {}

        parsed = mo_sql_parsing.parse(line)
        if parsed.get('select') is None:
            raise ValueError
        
        if isinstance(parsed['select'], list):
            ret['fields'] = [cls._compile_column(node) for node in parsed['select']]
        else:
            ret['fields'] = [cls._compile_column(parsed['select'])]
        for field in ret['fields']:
            if field.startswith('*'):
                raise ValueError

        if isinstance(parsed['from'], list):
            ret['tables'] = [cls._compile_column(parsed['from'][0])]
            if len(parsed['from']) > 1:
                ret['joins'] = []
                for join in parsed['from'][1:]:
                    if 'join' not in join:
                        raise ValueError
                    ret['tables'].append(cls._compile_column(join['join']))
                    ret['joins'].append(mo_sql_parsing.format(join['on']))
        else:
            ret['tables'] = [cls._compile_column(parsed['from'])]

        if parsed.get('where') is not None:
            ret['where'] = mo_sql_parsing.format(parsed['where'])

        if parsed.get('groupby') is not None:
            ret['group_by'] = cls._compile_column(parsed['groupby'])

        if parsed.get('having') is not None:
            ret['having'] = mo_sql_parsing.format(parsed['having'])

        if parsed.get('orderby') is not None:
            ret['order_by'] = []
            if isinstance(parsed['orderby'], dict):
                orderbys = [parsed['orderby']]
            else:
                orderbys = parsed['orderby']
            ret['order_by'] = [(node['value'], node.get('sort').upper() if 'sort' in node else 'ASC') for node in orderbys]

        if parsed.get('limit') is not None:
            ret['limit'] = parsed['limit']

        if parsed.get('offset') is not None:
            ret['offset'] = parsed['offset']

        return LeaguepediaQuery(**ret)

class LeaguepediaConnection:

    address: str
    path: str

    def __init__(self, address: str, path: str):
        self.address = address
        self.path = path

    def cursor(self):
        if self.address is None:
            raise ConnectionClosedError
        return LeaguepediaCursor(self.address, self.path)

    def close(self):
        self.address = None

    def commit(self):
        pass

    def rollback(self):
        pass

class LeaguepediaCursor:

    site: mwclient.Site
    rows: List[Any]
    arraysize: int
    description: List[Mapping[str, Union[str, int]]]

    def __init__(self, address: str, path: str):
        self.address = address
        self.site = mwclient.Site(address, path=path)
        self.rows = []
        self.arraysize = 1

    def setinputsizes(self, size):
        pass

    def setoutputsize(self, size, column = None):
        pass

    def _inject_params(self, stmt: str, params: Iterable[Union[str, int, float]]):
        _params = list(params)
        idx = stmt.find('?')
        while idx != -1:
            if len(stmt) > idx + 1 and stmt[idx + 1] == '?':
                idx += 1
            else:
                param = _params.pop(0)
                if isinstance(param, str):
                    stmt = stmt[:idx] + f"'{param}'" + stmt[idx+1:]
                elif isinstance(param, int) or isinstance(param, float):
                    stmt = stmt[:idx] + f'{param}' + stmt[idx+1:]
            idx = stmt.find('?', idx + 1)
        return stmt

    def execute(self, statement: str, args: Iterable[str] = [], log_queries: bool = False):
        if len(args) > 0:
            statement = self._inject_params(statement, args)
        compiled_fields = LeaguepediaQuery.parse(statement)
        if log_queries:
            print('Querying', {
                'tables': ','.join(compiled_fields.tables),
                'fields': ','.join(compiled_fields.fields),
                'where': compiled_fields.where,
                'join_on': ','.join(compiled_fields.joins) if compiled_fields.joins is not None else None,
                'order_by': ','.join([f'{col} {order}' for col, order in compiled_fields.order_by]),
                'group_by': compiled_fields.group_by,
                'having': compiled_fields.having,
                'format': 'json',
                'limit': compiled_fields.limit,
                'offset': compiled_fields.offset,
            })
        league_response = self.site.api(
            'cargoquery',
            tables=','.join(compiled_fields.tables),
            fields=','.join(compiled_fields.fields),
            where=compiled_fields.where,
            join_on=','.join(compiled_fields.joins) if compiled_fields.joins is not None else None,
            order_by=','.join([f'{col} {order}' for col, order in compiled_fields.order_by]),
            group_by=compiled_fields.group_by,
            having=compiled_fields.having,
            format='json',
            limit=compiled_fields.limit,
            offset=compiled_fields.offset,
        )
        parsed = json.dumps(league_response)
        decoded = json.loads(parsed)
        self.rows = decoded['cargoquery']
        if len(self.rows) > 0:
            self.description = [{'name': k, 'value': 'NUMBER' if isinstance(self.rows[0][k], int) else 'STRING'} for k in self.rows[0].keys()]

    def executemany(self, statement, param_groups: Iterable[Iterable[str]] = [], log_queries: bool = False):
        rows = []
        if len(param_groups) == 0:
            self.execute(statement, log_queries=log_queries)
            return

        for params in param_groups:
            self.execute(statement, args=params, log_queries=log_queries)
            rows.extend(self.rows)
        self.rows = rows

    def callproc(self, procname, params: Iterable[Iterable[str]] = []):
        raise NotImplementedError

    def fetchone(self):
        return self.rows.pop(0)['title']

    def fetchall(self):
        return self.fetchmany(len(self.rows))

    def fetchmany(self, cnt: Optional[int] = None):
        if cnt is None:
            cnt = self.arraysize
        rows = self.rows
        self.rows = []
        for row in rows:
            yield row['title']

    @property
    def rowcount(self):
        return len(self.rows)


def connect(address: str = 'lol.fandom.com', path: str = '/'):
    return LeaguepediaConnection(address, path)
