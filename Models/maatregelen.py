# SPDX-License-Identifier: EUPL-1.2
# Copyright (C) 2018 - 2020 Provincie Zuid-Holland

import marshmallow as MM
from Endpoints.endpoint import Base_Schema
from Endpoints.references import UUID_Reference
from Endpoints.validators import HTML_Validate
from Models.werkingsgebieden import Werkingsgebieden_Schema

from globals import default_user_uuid
class Maatregelen_Schema(Base_Schema):
    Eigenaar_1 = MM.fields.UUID(
        default=default_user_uuid, missing=default_user_uuid, allow_none=True, userfield=True, obprops=[])
    Eigenaar_2 = MM.fields.UUID(
        default=default_user_uuid, missing=default_user_uuid, allow_none=True, userfield=True, obprops=[])
    Portefeuillehouder_1 = MM.fields.UUID(
        default=default_user_uuid, missing=default_user_uuid, allow_none=True, obprops=[])
    Portefeuillehouder_2 = MM.fields.UUID(
        default=default_user_uuid, missing=default_user_uuid, allow_none=True, obprops=[])
    Opdrachtgever = MM.fields.UUID(
        default=default_user_uuid, missing=default_user_uuid, allow_none=True, obprops=[])
    Titel = MM.fields.Str(required=True, validate=[HTML_Validate], obprops=['search_title'])
    Omschrijving = MM.fields.Str(missing=None, validate=[HTML_Validate], obprops=['search_description'])
    Toelichting = MM.fields.Str(missing=None, validate=[HTML_Validate], obprops=[])
    Toelichting_Raw = MM.fields.Method(missing=None, obprops=[])
    Status = MM.fields.Str(missing=None, validate=[MM.validate.OneOf([
        "Definitief ontwerp GS",
        "Definitief ontwerp GS concept",
        "Definitief ontwerp PS",
        "Niet-Actief",
        "Ontwerp GS",
        "Ontwerp GS Concept",
        "Ontwerp in inspraak",
        "Ontwerp PS",
        "Uitgecheckt",
        "Vastgesteld",
        "Vigerend",
        "Vigerend gearchiveerd"])],
        obprops=[])
    Weblink = MM.fields.Str(missing=None, obprops=[])
    Gebied = MM.fields.UUID(missing=None, obprops=[])
    Gebied_Duiding = MM.fields.Str(allow_none=True, missing="Indicatief",
                                   validate=MM.validate.OneOf(["Indicatief", "Exact"]), obprops=[])
    Tags = MM.fields.Str(missing=None, obprops=[])
    Aanpassing_Op = MM.fields.UUID(
        missing=None, default=None, obprops=['excluded_post'])
    
    class Meta(Base_Schema.Meta):
        slug = 'maatregelen'
        table = 'Maatregelen'
        read_only = False
        ordered = True
        searchable = True
        references = {'Gebied': UUID_Reference(
                'Werkingsgebieden', Werkingsgebieden_Schema)}
        status_conf = ('Status', 'Vigerend')
