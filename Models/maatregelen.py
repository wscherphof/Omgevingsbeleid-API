# SPDX-License-Identifier: EUPL-1.2
# Copyright (C) 2018 - 2020 Provincie Zuid-Holland

import marshmallow as MM
from Endpoints.endpoint import Base_Schema
from Endpoints.references import UUID_Reference

from Models.werkingsgebieden import Werkingsgebieden_Schema


class Maatregelen_Schema(Base_Schema):
    Titel = MM.fields.Str(required=True, obprops=['search_title'])
    Omschrijving = MM.fields.Str(missing=None, obprops=['search_description'])
    Toelichting = MM.fields.Str(missing=None, obprops=[])
    Toelichting_Raw = MM.fields.Method(missing=None, obprops=[])
    Status = MM.fields.Str(missing=None, validate=MM.validate.OneOf([
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
        "Vigerend gearchiveerd"]),
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