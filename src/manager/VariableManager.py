import time
from typing import Dict, Optional, List, Tuple, Union
from pysondb.errors import IdDoesNotExistError

from src.manager.DatabaseManager import DatabaseManager
from src.model.entity.Variable import Variable
from src.model.entity.Selectable import Selectable
from src.model.enum.VariableType import VariableType
from src.model.enum.VariableUnit import VariableUnit
from src.model.enum.AnimationEntranceEffect import AnimationEntranceEffect
from src.model.enum.AnimationExitEffect import AnimationExitEffect
from src.model.enum.AnimationSpeed import AnimationSpeed
from src.utils import get_keys, enum_to_str

SELECTABLE_BOOLEAN = {"1": "✅", "0": "❌"}


class VariableManager:

    TABLE_NAME = "settings"
    TABLE_MODEL = [
        "description",
        "editable",
        "name",
        "plugin",
        "selectables",
        "type",
        "unit",
        "value"
    ]

    def __init__(self, database_manager: DatabaseManager):
        self._database_manager = database_manager
        self._db = database_manager.open(self.TABLE_NAME, self.TABLE_MODEL)
        self._var_map = {}
        self.reload()

    def set_variable(self, name: str, value, type: VariableType, editable: bool, description: str, plugin: Optional[None] = None, selectables: Optional[Dict[str, str]] = None, unit: Optional[VariableUnit] = None) -> Variable:
        if isinstance(value, bool) and value:
            value = '1'
        elif isinstance(value, bool) and not value:
            value = '0'

        if type == VariableType.BOOL:
            selectables = SELECTABLE_BOOLEAN

        default_var = {
            "name": name,
            "value": value,
            "type": type.value,
            "editable": editable,
            "description": description,
            "plugin": plugin,
            "unit": unit.value if unit else None,
            "selectables": ([{"key": key, "label": label} for key, label in selectables.items()]) if isinstance(selectables, dict) else None
        }
        variable = self.get_one_by_name(default_var['name'])

        if not variable:
            self.add_form(default_var)
            variable = self.get_one_by_name(default_var['name'])
        else:
            same_selectables = get_keys(default_var, 'selectables') == get_keys(variable, 'selectables')

            if variable.description != default_var['description']:
                self._db.update_by_id(variable.id, {"description": default_var['description']})

            if variable.unit != default_var['unit']:
                self._db.update_by_id(variable.id, {"unit": default_var['unit']})

            if not same_selectables:
                self._db.update_by_id(variable.id, {"selectables": default_var['selectables']})

        if variable.name == 'last_restart':
            self._db.update_by_id(variable.id, {"value": time.time()})

        return variable

    def reload(self, lang_map: Optional[Dict] = None) -> None:
        default_vars = [
            {"name": "lang", "value": "en", "type": VariableType.SELECT_SINGLE, "editable": True, "description": lang_map['settings_variable_desc_lang'] if lang_map else "", "selectables": {"en": "English", "fr": "French"}},
            {"name": "fleet_enabled", "value": False, "type": VariableType.BOOL, "editable": True, "description": lang_map['settings_variable_desc_fleet_enabled'] if lang_map else ""},
            {"name": "external_url", "value": "", "type": VariableType.STRING, "editable": True, "description": lang_map['settings_variable_desc_external_url'] if lang_map else ""},
            {"name": "slide_upload_limit", "value": 32 * 1024 * 1024, "unit": VariableUnit.BYTE,  "type": VariableType.INT, "editable": True, "description": lang_map['settings_variable_desc_slide_upload_limit'] if lang_map else ""},
            {"name": "slide_animation_enabled", "value": False, "type": VariableType.BOOL, "editable": True, "description": lang_map['settings_variable_desc_slide_animation_enabled'] if lang_map else ""},
            {"name": "slide_animation_entrance_effect", "value": AnimationEntranceEffect.FADE_IN.value, "type": VariableType.SELECT_SINGLE, "editable": True, "description": lang_map['settings_variable_desc_slide_animation_entrance_effect'] if lang_map else "", "selectables": AnimationEntranceEffect.get_values()},
            {"name": "slide_animation_exit_effect", "value": AnimationExitEffect.NONE.value, "type": VariableType.SELECT_SINGLE, "editable": True, "description": lang_map['settings_variable_desc_slide_animation_exit_effect'] if lang_map else "", "selectables": AnimationExitEffect.get_values()},
            {"name": "slide_animation_speed", "value": AnimationSpeed.NORMAL.value, "type": VariableType.SELECT_SINGLE, "editable": True, "description": lang_map['settings_variable_desc_slide_animation_speed'] if lang_map else "", "selectables": AnimationSpeed.get_values(lang_map)},
            {"name": "last_restart", "value": time.time(), "type": VariableType.TIMESTAMP, "editable": False, "description": lang_map['settings_variable_desc_ro_editable'] if lang_map else ""},
            {"name": "last_slide_update", "value": time.time(), "type": VariableType.TIMESTAMP, "editable": False, "description": lang_map['settings_variable_desc_ro_last_slide_update'] if lang_map else ""},
        ]

        for default_var in default_vars:
            self.set_variable(**default_var)

        self._var_map = self.prepare_variable_map()

    def map(self) -> dict:
        return self._var_map

    def prepare_variable_map(self) -> Dict[str, Variable]:
        return self.list_to_map(self.get_all())

    @staticmethod
    def list_to_map(list: List[Variable]) -> Dict[str, Variable]:
        var_map = {}

        for var in list:
            var_map[var.name] = var

        return var_map

    @staticmethod
    def hydrate_object(raw_variable: dict, id: Optional[str] = None) -> Variable:
        if id:
            raw_variable['id'] = id

        if 'selectables' in raw_variable and raw_variable['selectables']:
            raw_variable['selectables'] = [Selectable(**selectable) for selectable in raw_variable['selectables']]

        return Variable(**raw_variable)

    @staticmethod
    def hydrate_dict(raw_variables: dict) -> List[Variable]:
        return [VariableManager.hydrate_object(raw_variable, raw_id) for raw_id, raw_variable in raw_variables.items()]

    @staticmethod
    def hydrate_list(raw_variables: list) -> List[Variable]:
        return [VariableManager.hydrate_object(raw_variable) for raw_variable in raw_variables]

    def get(self, id: str) -> Optional[Variable]:
        try:
            return self.hydrate_object(self._db.get_by_id(id), id)
        except IdDoesNotExistError:
            return None

    def get_by(self, query) -> List[Variable]:
        return self.hydrate_dict(self._db.get_by_query(query=query))

    def get_by_prefix(self, prefix: str) -> List[Variable]:
        return self.hydrate_dict(self._db.get_by_query(query=lambda v: v['name'].startswith(prefix)))

    def get_by_plugin(self, plugin: str) -> List[Variable]:
        return self.hydrate_dict(self._db.get_by_query(query=lambda v: v['plugin'] == plugin))

    def get_one_by_name(self, name: str) -> Optional[Variable]:
        return self.get_one_by(query=lambda v: v['name'] == name)

    def get_one_by(self, query) -> Optional[Variable]:
        object = self._db.get_by_query(query=query)
        variables = self.hydrate_dict(object)
        if len(variables) == 1:
            return variables[0]
        elif len(variables) > 1:
            raise Error("More than one result for query")
        return None

    def get_all(self) -> List[Variable]:
        raw_variables = self._db.get_all()

        if isinstance(raw_variables, dict):
            return VariableManager.hydrate_dict(raw_variables)

        return VariableManager.hydrate_list(raw_variables)

    def get_editable_variables(self, plugin: bool = True) -> List[Variable]:
        query = lambda v: (not plugin and not isinstance(v['plugin'], str)) or (plugin and isinstance(v['plugin'], str))
        return [variable for variable in self.get_by(query=query) if variable.editable]

    def get_readonly_variables(self) -> List[Variable]:
        return [variable for variable in self.get_all() if not variable.editable]

    def update_form(self, id: str, value: Union[int, bool, str]) -> None:
        self._db.update_by_id(id, {"value": value})

    def update_by_name(self, name: str, value) -> Optional[Variable]:
        return self._db.update_by_query(query=lambda v: v['name'] == name, new_data={"value": value})

    def add_form(self, variable: Union[Variable, Dict]) -> None:
        db_variable = variable

        if not isinstance(variable, dict):
            db_variable = variable.to_dict()
            del db_variable['id']

        self._db.add(db_variable)

    def delete(self, id: str) -> None:
        self._db.delete_by_id(id)

    def to_dict(self, variables: List[Variable]) -> dict:
        return [variable.to_dict() for variable in variables]
