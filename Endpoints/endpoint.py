# SPDX-License-Identifier: EUPL-1.2
# Copyright (C) 2018 - 2020 Provincie Zuid-Holland

import datetime
import re
import pprint
import marshmallow as MM
from marshmallow.schema import Schema
import pyodbc
from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restful import Resource
from globals import (db_connection_settings, max_datetime, min_datetime,
                     null_uuid, row_to_dict)

from Endpoints.base_schema import Base_Schema
from Endpoints.errors import (handle_does_not_exists, handle_empty, handle_integrity_exception, handle_no_status,
                              handle_odbc_exception, handle_read_only,
                              handle_validation_exception,
                              handle_empty,
                              handle_read_only,
                              handle_does_not_exists,
                              handle_no_status,
                              handle_integrity_exception,
                              handle_odbc_exception,
                              handle_validation_exception,
                              handle_validation_filter_exception,
                              handle_queryarg_exception)
from Endpoints.references import merge_references, store_references
from Endpoints.comparison import compare_objects


def save_object(new_object, schema, cursor):
    """Saves an object to a table, retrieves and stores the generated values and return the object.

    Args:
        new_object (dict): The object to be stored 
        schema (marshmallow.Schema): The schema of the object
        cursor (pyodbc.cursor): A cursor with an active database connection

    Returns:
        dict: The object that was stored, new values filled in
    """
    references = schema.fields_with_props('referencelist')
    reference_cache = {}
    for ref in references:
        if ref in new_object:
            reference_cache[ref] = new_object.pop(ref)

    column_names, values = tuple(zip(*new_object.items()))
    parameter_marks = ', '.join(['?'] * len(column_names))
    query = f'''INSERT INTO {schema.Meta.table} ({', '.join(column_names)}) OUTPUT inserted.UUID, inserted.ID VALUES ({parameter_marks})'''
    cursor.execute(query, *values)

    output = cursor.fetchone()
    new_object['UUID'] = output[0]
    new_object['ID'] = output[1]

    for ref in reference_cache:
        new_object[ref] = reference_cache[ref]

    new_object = store_references(new_object, schema, cursor)

    # Up to here we have stored the references, and the object itself
    included_fields = ', '.join(
        [field for field in schema().fields_without_props('referencelist')])
    retrieve_query = f'''SELECT {included_fields} FROM {schema.Meta.table} WHERE UUID = ?'''
    return get_objects(retrieve_query, [new_object['UUID']], schema(), cursor)[0]


def get_objects(query, query_args, schema, cursor, inline=True):
    """Retrieves objects using a given query

    Args:
        query (string): Sql query to use
        query_args (list): Arguments to fill the query with (using '?' notation from PyODBC)
        schema (marshmallow.Schema): The schema of the object
        cursor (pyodbc.Cursor): A cursor with an active database connection

    Returns:
        list: A collection of objects that resulted out of the query
    """
    query_result = map(row_to_dict, cursor.execute(query, *query_args))
    # Load the objects to ensure validation
    result_objecten = list(map(schema.load, query_result))
    result_objecten = schema.dump(result_objecten, many=True)

    for obj in result_objecten:
        obj = merge_references(obj, schema, cursor, inline)

    return(result_objecten)


class QueryArgError(Exception):
    pass


def parse_query_args(q_args, valid_filters, filter_schema):
    """parses both filter values and pagination setting from the query arguments
    Args:
        q_args (Mapping): the query arguments (retrieved from request.args)
        valid_filters (List): Valid fields to filter on
        filter_schema (MM.Schema): Schema to validate filters on

    Returns:
        Dict: A dictionary that contains the filters (Dict) and the Limit (Int) & Offset (Int)
    """
    parsed = {}
    parsed['limit'] = q_args.get('limit')
    parsed['offset'] = q_args.get('offset', 0)
    parsed['filters'] = None

    if parsed['limit']:
        if int(parsed['limit']) <= 0:
            raise QueryArgError(f"Limit must be > 0")

    if parsed['offset'] and int(parsed['offset']) < 0:
        raise QueryArgError(f"Offset must be > 0")

    filters_strf = q_args.get('filters')
    if filters_strf:
        parsed['filters'] = dict([tuple(filter.split(':'))
                                  for filter in filters_strf.split(',')])
        invalids = [f for f in parsed['filters'].keys()
                    if f not in valid_filters]
        if invalids:
            raise QueryArgError(
                f"Filter(s) '{' '.join(invalids)}' invalid for this endpoint. Valid filters: '{', '.join(valid_filters)}''")
        parsed['filters'] = filter_schema.load(parsed['filters'])
    return parsed


class Schema_Resource(Resource):
    """
    A base class that accepts a Marshmallow schema as configuration
    """

    def __init__(self, schema):
        self.schema = schema


class Lineage(Schema_Resource):
    """
    A lineage is a list of all object that have the same ID, ordered by modified date.
    This represents the history of an object in our database.
    """
    @jwt_required()
    def get(self, id):
        """
        GET endpoint for a lineage.
        """
        try:
            q_args = parse_query_args(
                request.args, self.schema().fields_without_props('referencelist'), self.schema(partial=True))
        except QueryArgError as e:
            # Invalid filter keys
            return handle_queryarg_exception(e)
        except MM.exceptions.ValidationError as e:
            # Invalid filter values
            return handle_validation_filter_exception(e)

        # Retrieve all the fields we want to query
        included_fields = ', '.join(
            [field for field in self.schema().fields_without_props('referencelist')])

        query = f'''SELECT {included_fields} FROM {self.schema().Meta.table} WHERE ID = ?'''

        # Id is required
        query_args = [id]

        if filters := q_args['filters']:
            query += ' AND ' + \
                'OR '.join(f'{key} = ? ' for key in filters)
            query_args = [filters[key] for key in filters]

        query += ''' AND UUID != '00000000-0000-0000-0000-000000000000' ORDER BY Modified_Date DESC'''

        query += " OFFSET ? ROWS"
        query_args.append(int(q_args['offset']))

        if limit := q_args['limit']:
            query += " FETCH NEXT ? ROWS ONLY"
            query_args.append(int(limit))

        with pyodbc.connect(db_connection_settings) as connection:
            cursor = connection.cursor()
            return(get_objects(query, query_args, self.schema(), cursor))

    @jwt_required()
    def patch(self, id):
        """
        PATCH endpoint for a lineage.
        """
        if self.schema.Meta.read_only or self.schema.Meta.read_only:
            return handle_read_only()

        if request.json is None:
            return handle_empty()

        patch_schema = self.schema(
            exclude=self.schema.fields_with_props('exluded_patch'),
            unknown=MM.RAISE,
            partial=True
        )

        request_time = datetime.datetime.now()

        with pyodbc.connect(db_connection_settings, autocommit=False) as connection:
            cursor = connection.cursor()

            old_object = None

            query = f'SELECT TOP(1) * FROM {self.schema.Meta.table} WHERE ID = ? ORDER BY Modified_Date DESC'

            old_object = get_objects(
                query, [id], self.schema(), cursor, inline=False)[0]

            try:
                changes = patch_schema.load(request.json)
            except MM.exceptions.ValidationError as e:
                return handle_validation_exception(e)

            old_object = self.schema().load(old_object)

            new_object = {**old_object, **changes}

            new_object.pop('UUID')
            new_object['Modified_Date'] = request_time
            new_object['Modified_By'] = get_jwt_identity()['UUID']

            try:
                new_object = save_object(
                    new_object, self.schema, cursor)
            except pyodbc.IntegrityError as e:
                return handle_integrity_exception(e)
            except pyodbc.DatabaseError as e:
                return handle_odbc_exception(e)

            connection.commit()
            return new_object, 200


class FullList(Schema_Resource):
    """
    A list of all the different lineages available in the database, 
    showing the latests version of each object's lineage.
    """

    @jwt_required()
    def get(self):
        """
        GET endpoint for a list of objects, shows the last object for each lineage
        """
        try:
            q_args = parse_query_args(
                request.args, self.schema().fields_without_props('referencelist'), self.schema(partial=True))
        except QueryArgError as e:
            # Invalid filter keys
            return handle_queryarg_exception(e)
        except MM.exceptions.ValidationError as e:
            # Invalid filter values
            return handle_validation_filter_exception(e)

        # Retrieve all the fields we want to query
        included_fields = ', '.join(
            [field for field in self.schema().fields_without_props('referencelist')])

        query = f'''SELECT {included_fields} FROM (SELECT {included_fields}, 
                        ROW_NUMBER() OVER (PARTITION BY [ID] ORDER BY [Modified_Date] DESC) [RowNumber] 
                        FROM {self.schema().Meta.table}) T WHERE RowNumber = 1'''

        query_args = []

        if filters := q_args['filters']:
            query += ' AND ' + \
                'OR '.join(f'{key} = ? ' for key in filters)
            query_args = [filters[key] for key in filters]

        query += " AND UUID != '00000000-0000-0000-0000-000000000000' ORDER BY Modified_Date DESC"

        query += " OFFSET ? ROWS"
        query_args.append(int(q_args['offset']))

        if limit := q_args['limit']:
            query += " FETCH NEXT ? ROWS ONLY"
            query_args.append(int(limit))

        with pyodbc.connect(db_connection_settings, autocommit=False) as connection:
            cursor = connection.cursor()
            return(get_objects(query, query_args, self.schema(), cursor))

    @jwt_required()
    def post(self):
        """
        POST endpoint for this object.
        """
        if self.schema.Meta.read_only:
            return handle_read_only

        if request.json is None:
            return handle_empty

        post_schema = self.schema(
            exclude=self.schema.fields_with_props(
                'excluded_post'),
            unknown=MM.utils.RAISE)

        request_time = datetime.datetime.now()

        with pyodbc.connect(db_connection_settings, autocommit=False) as connection:
            cursor = connection.cursor()

            try:
                new_object = post_schema.load(request.get_json())
            except MM.exceptions.ValidationError as e:
                return handle_validation_exception(e)

            new_object['Created_By'] = get_jwt_identity()['UUID']
            new_object['Created_Date'] = request_time
            new_object['Modified_Date'] = new_object['Created_Date']
            new_object['Modified_By'] = new_object['Created_By']

            try:
                new_object = save_object(
                    new_object, self.schema, cursor)
            except pyodbc.IntegrityError as e:
                return handle_integrity_exception(e)
            except pyodbc.DatabaseError as e:
                return handle_odbc_exception(e), 500
            except MM.exceptions.ValidationError as e:
                return handle_validation_exception(e)

            connection.commit()
            return new_object, 201


class ValidList(Schema_Resource):
    """
    A list of all the different lineages available in the database, 
    showing the latests valid version of each object's lineage.

    Not availabe if the schema's status_conf is None
    """

    def get(self):
        """
        GET endpoint for a list of objects, shows the last valid object for each lineage
        """
        try:
            q_args = parse_query_args(
                request.args, self.schema().fields_without_props('referencelist'), self.schema(partial=True))
        except QueryArgError as e:
            # Invalid filter keys
            return handle_queryarg_exception(e)
        except MM.exceptions.ValidationError as e:
            # Invalid filter values
            return handle_validation_filter_exception(e)

        # Retrieve all the fields we want to query
        included_fields = ', '.join(
            [field for field in self.schema().fields_without_props('referencelist')])

        if not self.schema.Meta.status_conf:
            query = f'''SELECT {included_fields} FROM (SELECT {included_fields}, 
                        ROW_NUMBER() OVER (PARTITION BY [ID] ORDER BY [Modified_Date] DESC) [RowNumber] 
                        FROM {self.schema().Meta.table}) T WHERE RowNumber = 1'''

            query_args = []
        else:
            status_field, status_value = self.schema.Meta.status_conf

            query = f'''SELECT {included_fields} FROM
                        (SELECT {included_fields}, Row_number() OVER (partition BY [ID]
                        ORDER BY [Modified_date] DESC) [RowNumber]
                        FROM {self.schema().Meta.table}
                        WHERE {status_field} = ? AND UUID != '00000000-0000-0000-0000-000000000000') T 
                        WHERE rownumber = 1'''

            query_args = [status_value]

        if filters := q_args['filters']:
            query += ' AND ' + \
                'OR '.join(f'{key} = ? ' for key in filters)
            query_args = [filters[key] for key in filters]

        query += " AND UUID != '00000000-0000-0000-0000-000000000000' ORDER BY [Modified_date] DESC"

        query += " OFFSET ? ROWS"
        query_args.append(int(q_args['offset']))

        if limit := q_args['limit']:
            query += " FETCH NEXT ? ROWS ONLY"
            query_args.append(int(limit))

        with pyodbc.connect(db_connection_settings) as connection:
            cursor = connection.cursor()
            return(get_objects(query, query_args, self.schema(), cursor))


class ValidLineage(Schema_Resource):
    """
    A lineage is a list of all object that have the same ID, ordered by modified date.
    This represents the history of an object valid states in our database.
    """

    def get(self, id):
        """
        GET endpoint for a lineage.
        """
        if not self.schema.Meta.status_conf:
            return handle_no_status()

        with pyodbc.connect(db_connection_settings) as connection:
            cursor = connection.cursor()

            # Retrieve all the fields we want to query
            included_fields = ', '.join(
                [field for field in self.schema().fields_without_props('referencelist')])

            status_field, value = self.schema.Meta.status_conf

            query = f'''SELECT {included_fields} FROM {self.schema().Meta.table} WHERE ID = ? AND {status_field} = ? AND UUID != '00000000-0000-0000-0000-000000000000' ORDER BY Modified_Date DESC '''

            return(get_objects(query, [id, value], self.schema(), cursor))


class SingleVersion(Schema_Resource):
    """
    This represents a single version of an object, identified by it's UUID.
    """

    def get(self, uuid):
        """
        Get endpoint for a single object
        """
        with pyodbc.connect(db_connection_settings) as connection:
            cursor = connection.cursor()

            # Retrieve all the fields we want to query
            included_fields = ', '.join(
                [field for field in self.schema().fields_without_props('referencelist')])

            query = f'SELECT {included_fields} FROM {self.schema().Meta.table} WHERE UUID = ?'
            result = get_objects(query, [uuid], self.schema(), cursor)
            if not result:
                return handle_does_not_exists()
            return(result[0])


class Changes(Schema_Resource):
    """
    This represents the changes between two objects, identified by their UUIDs.
    """

    def get(self, old_uuid, new_uuid):
        """
        Get endpoint for a single object
        """
        with pyodbc.connect(db_connection_settings) as connection:
            cursor = connection.cursor()

            # Retrieve all the fields we want to query
            included_fields = ', '.join(
                [field for field in self.schema().fields_without_props('referencelist')])

            query = f'SELECT {included_fields} FROM {self.schema().Meta.table} WHERE UUID IN (?, ?)'

            both_obj = get_objects(
                query, [old_uuid, new_uuid], self.schema(), cursor)

            old_object = None
            new_object = None
            for _obj in both_obj:
                if _obj['UUID'] == old_uuid:
                    old_object = _obj
                if _obj['UUID'] == new_uuid:
                    new_object = _obj

            if not old_object:
                return handle_does_not_exists(old_uuid)
            if not new_object:
                return handle_does_not_exists(new_uuid)
            return({
                'old': old_object,
                'changes': compare_objects(self.schema(), old_object, new_object)
            }), 200
