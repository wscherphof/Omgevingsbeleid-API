# SPDX-License-Identifier: EUPL-1.2
# Copyright (C) 2018 - 2020 Provincie Zuid-Holland

import marshmallow as MM
from flask_restful import Resource
from flask_jwt_extended import jwt_required
import pyodbc
from globals import null_uuid, db_connection_settings
import uuid

class Gebruikers_Schema(MM.Schema):
    UUID = MM.fields.UUID(required=True)
    Gebruikersnaam = MM.fields.Str(required=True)
    Rol = MM.fields.Str(missing=None)
    Status = MM.fields.Str(missing=None)

    class Meta:
        table = 'Gebruikers'
        read_only = True
        ordered = True
        searchable = False

    @MM.post_dump()
    def uppercase(self, dumped, many):
        """
        Ensure UUID's are uppercase.
        """
        for field in dumped:
            try:
                uuid.UUID(dumped[field])
                dumped[field] = dumped[field].upper()
            except:
                pass
        return dumped


class Gebruiker(Resource):
    """Deze resource vertegenwoordigd de Gebruikers van de applicaite"""
    @jwt_required()
    def get(self, gebruiker_uuid=None):
        with pyodbc.connect(db_connection_settings) as cnx:
            cur = cnx.cursor()
            if gebruiker_uuid:
                gebruikers = list(cur.execute(
                    'SELECT * FROM Gebruikers WHERE UUID = ?', gebruiker_uuid))

                if not gebruikers:
                    return {'message': f"Gebruiker met UUID {gebruiker_uuid} is niet gevonden"}, 400

                schema = Gebruikers_Schema()
                return(schema.dump(gebruikers[0]))
            else:
                gebruikers = cur.execute(
                    f"SELECT * FROM Gebruikers WHERE UUID != '{null_uuid}'")
                schema = Gebruikers_Schema()
                return(schema.dump(gebruikers, many=True))
