#!/usr/bin/env python3

import pandas as pd
from pydantic import BaseModel
from typing import Union
import base64
import json
import zlib
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz.process import extract

app = FastAPI(
    title="Translator",
    version="1.0.0",
    redoc_url=None,
    root_path="/translator")
templates = Jinja2Templates(directory="templates")

json_tables = {
    "job_class": "./job_classes.json",
    "skill":     "./skill_list.json",
}

origins: list = [
    "http://localhost",
    "https://rodb.aws.0nyx.net",
    "https://rowebtool.gungho.jp",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["POST", "GET", "PUT", "DELETE", "HEAD", "OPTIONS"],
    allow_headers=["Origin", "Authorization", "Accept"],
)

class CharacterDataVersion1(BaseModel):
    format_version: int = 1
    overwrite: bool = True # True: initして上書き, False: Merge

    status: Union[dict, None] = None
    skills: Union[dict, None] = None
    equipments: Union[dict, None] = None
    items: Union[dict, None] = None
    supports: Union[dict, None] = None
    additional_info: Union[dict, None] = None

    def to_dict(self, compact: bool) -> dict:
        data_dict: dict[str] = {
            "format_version" : self.format_version,
            "overwrite" : self.overwrite,
            "status" : {
            },
            "skills": {
            },
            "equipments": {
            },
            "items": {
            },
            "supports": {
            },
            "additional_info": {
            }
        }

        if self.status is not None:
            if "job_class_localization" in self.status:
                job_class_table: dict = None
                with open(json_tables["job_class"], "r", encoding="utf-8") as fp:
                    job_class_table = json.load(fp)

                    for value in job_class_table:
                        if value["display_name"] == self.status["job_class_localization"]:
                            data_dict["status"]["job_class"] = value["class"]
                            data_dict["status"]["ratorio_job_id_num"] = value["ratorio_job_id_num"]
                            break

                if compact == True:
                    del self.status["job_class_localization"]

            if "hp_max" in self.status:
                try:
                    data_dict["additional_info"]["hp_base_point"] = int(self.status["hp_max"])
                except ValueError:
                    pass
                del self.status["hp_max"]
            if "sp_max" in self.status:
                try:
                    data_dict["additional_info"]["sp_base_point"] = int(self.status["sp_max"])
                except ValueError:
                    pass
                del self.status["sp_max"]

            for key in self.status.keys():
                try:
                    data_dict["status"][key] = int(self.status[key])
                except ValueError:
                    data_dict["status"][key] = self.status[key]

        if self.skills is not None:
            if "localization" in self.skills:
                skill_table: dict = None
                with open(json_tables["skill"], "r", encoding="utf-8") as fp:
                    skill_table = json.load(fp)

                remove_localization_list: list[str] = []
                for local_name, skill_lv in self.skills["localization"].items():
                    for idx, value in skill_table.items():
                        # 一番最初に合致したスキルとなる(skill tableには同じ名前のスキルがあることも)
                        if "name" in value and value["name"] == local_name:
                            data_dict["skills"][idx] = {}
                            data_dict["skills"][idx]["lv"] = skill_lv
                            remove_localization_list.append(local_name)
                            break

                for local_name in remove_localization_list:
                    del self.skills["localization"][local_name]

                if len(self.skills["localization"]) == 0:
                    del self.skills["localization"]

            for key in self.skills.keys():
                data_dict["skills"][key] = self.skills[key]

        if self.equipments is not None:
            for key in self.equipments.keys():
                data_dict["equipments"][key] = self.equipments[key]

        if self.items is not None:
            for key in self.items.keys():
                data_dict["items"][key] = self.items[key]

        if self.items is not None:
            for key in self.items.keys():
                data_dict["supports"][key] = self.supports[key]

        if self.additional_info is not None:
            if "character_name" in self.additional_info:
                data_dict["additional_info"]["character_name"] = self.additional_info["character_name"]
            if "world_name" in self.additional_info:
                data_dict["additional_info"]["world_name"] = self.additional_info["world_name"]

            if "hp_base_point" in self.additional_info:
                try:
                    data_dict["additional_info"]["hp_base_point"] = int(self.additional_info["hp_base_point"])
                except ValueError:
                    pass
            if "sp_base_point" in self.additional_info:
                try:
                    data_dict["additional_info"]["sp_base_point"] = int(self.additional_info["sp_base_point"])
                except ValueError:
                    pass

        return data_dict

    def to_json(self, compact: bool = False, ensure_ascii: bool = False, sort_keys: bool = False, indent: int = 0) -> str:
        return json.dumps(self.to_dict(compact=compact), ensure_ascii=ensure_ascii, sort_keys=sort_keys, indent=indent)

@app.get("/")
async def index():
    return templates.TemplateResponse("index.html", {"request": {}})

@app.post("/")
async def translator(request: Request, data: CharacterDataVersion1):
    success: bool = True

    format_version: int = None

    if data.format_version >= 1:
        format_version = data.format_version

        return JSONResponse({
            "success": success,
            "format_version": format_version,
            "type": "json",
            "translated_data": data.to_json(indent=4)
        })

    else:
        success = False

        return JSONResponse({
            "success": success,
            "format_version": format_version
        })

@app.post("/rodb-simulator")
@app.post("/rodb-simulator/{version}")
async def rodb_simulator(request: Request, data: CharacterDataVersion1, version: int = 1):
    data_encoded: str = ""
    try:
        # dict => json
        data_json: str = data.to_json(indent=4)

        # json => copressed
        data_compressed: bytes = zlib.compress(data_json.encode("utf-8"))

        # zlib compressed => encoded
        data_encoded = base64.urlsafe_b64encode(data_compressed)

    except Exception as ex:
        return JSONResponse({
            "success": False,
            "message": str(ex)
        })

    else:
        return JSONResponse({
            "success": True,
            "url" : f"https://{request.url.hostname}/simulator/v{version}.html?{data_encoded}#main"
        })

@app.post("/roratorio-hub")
@app.post("/roratorio-hub/{version}")
async def roratorio_hub(request: Request, data: CharacterDataVersion1, version: int = 4):
    data_encoded: str = ""
    try:
        # dict => json
        data_json: str = data.to_json(indent=4)

        # json => copressed
        data_compressed: bytes = zlib.compress(data_json.encode("utf-8"))

        # zlib compressed => encoded
        data_encoded = base64.urlsafe_b64encode(data_compressed).decode("utf-8")

    except Exception as ex:
        return JSONResponse({
            "success": False,
            "message": str(ex)
        })

    else:
        return JSONResponse({
            "success": True,
            "url" : f"https://roratorio-hub.github.io/ratorio/ro{version}/m/calcx.html#rtx1:{data_encoded}"
        })

@app.get("/search/skill")
async def search_skill(request: Request, word: str = "", ratorio_skill_num: int = None):
    if word == "":
        return JSONResponse({
            "success": False,
            "message": "Please 'word' query."
        })

    skill_table: dict = None
    try:
        with open(json_tables["skill"], "r", encoding="utf-8") as fp:
            skill_table = json.load(fp)
    except:
        pass

    success: bool = False
    skill_name: str = None
    skill_data: dict = None
    for idx, value in skill_table.items():
        # 一番最初に合致したスキルとなる(skill tableには同じ名前のスキルがあることも)
        if "name" in value and value["name"] == word:
            success = True
            skill_name = idx
            skill_data = value
            break

    response: dict = {
        "success": success,
        "word": word,
        "skill_name": skill_name,
        "data" : skill_data
    }

    if ratorio_skill_num is not None:
        response["ratorio_skill_num"] = ratorio_skill_num

    return JSONResponse(response)

@app.get("/approximate_search/skill")
async def approximate_search_skill(request: Request, word: str = "", ratorio_skill_num: int = None):
    if word == "":
        return JSONResponse({
            "success": False,
            "message": "Please 'word' query."
        })

    skill_table: dict = None
    try:
        with open(json_tables["skill"], "r", encoding="utf-8") as fp:
            skill_table = json.load(fp)
    except:
        pass

    success: bool = False
    skill_name: str = None
    skill_data: dict = None

    choices: dict = {idx: value['name'] for idx, value in skill_table.items() if 'name' in value}
    # wordと最も近い物を１件だけ抽出
    result = extract(word, choices, limit = 1)

    if len(result) > 0:
        success = True
        skill_name = list(result[0])[2]
        skill_data = skill_table[skill_name]

    response: dict = {
        "success": success,
        "word": word,
        "skill_name": skill_name,
        "data" : skill_data
    }

    if ratorio_skill_num is not None:
        response["ratorio_skill_num"] = ratorio_skill_num

    return JSONResponse(response)

if __name__ == '__main__':
    uvicorn.run(app=app)
