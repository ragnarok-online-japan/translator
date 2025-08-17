#!/usr/bin/env python3

from pydantic import BaseModel
import base64
import json
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz.process import extract
import yaml
import zstandard as zstd

app = FastAPI(
    title="Translator",
    version="1.0.0",
    redoc_url=None,
    root_path="/translator")
templates = Jinja2Templates(directory="templates")

yaml_table = {
    "job"   : "./data/job.yaml",
    "skill" : "./data/skill.yaml"
}

origins: list = [
    "http://localhost",
    "https://ro-database.info",
    "https://rowebtool.gungho.jp",
    "https://roratorio-hub.github.io"
]

SKELETON_DICT: dict = {
    "format_version" : None,
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
    },
    "battle_info":{
    }
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["POST", "GET", "PUT", "DELETE", "HEAD", "OPTIONS"],
    allow_headers=["Origin", "Authorization", "Accept"],
)

class CharacterDataVersion2(BaseModel):
    format_version: int = 2

    status: dict = {}
    skills: dict = {}
    equipments: dict = {}
    items: dict = {}
    supports: dict = {}
    additional_info: dict  = {}

    def to_dict(self, compact: bool) -> dict:
        SKELETON_DICT["format_version"] = self.format_version

        if self.status is not None:
            if "job_class_localization" in self.status:
                # (ドラム) を消す
                self.status["job_class_localization"] = self.status["job_class_localization"].replace("(ドラム)","")

                job_map: dict = {}
                with open(yaml_table["job"], "r", encoding="utf-8") as fp:
                    job_map = yaml.safe_load(fp)

                    for idx, job in job_map.items():
                        if job["name_ja"] == self.status["job_class_localization"]:
                            SKELETON_DICT["status"]["job_id"] = idx
                            SKELETON_DICT["status"]["ratorio_job_id_num"] = job["_mig_id_num"]
                            break

                if compact == True:
                    del self.status["job_class_localization"]

            if "hp_max" in self.status:
                try:
                    SKELETON_DICT["additional_info"]["hp_base_point"] = int(self.status["hp_max"])
                except ValueError:
                    pass
                del self.status["hp_max"]
            if "sp_max" in self.status:
                try:
                    SKELETON_DICT["additional_info"]["sp_base_point"] = int(self.status["sp_max"])
                except ValueError:
                    pass
                del self.status["sp_max"]

            for key in self.status.keys():
                try:
                    SKELETON_DICT["status"][key] = int(self.status[key])
                except ValueError:
                    SKELETON_DICT["status"][key] = self.status[key]

        if self.skills is not None:
            if "localization" in self.skills:
                skill_map: dict = {}
                with open(yaml_table["skill"], "r", encoding="utf-8") as fp:
                    skill_map = yaml.safe_load(fp)

                remove_localization_list: list[str] = []
                for local_name, skill_lv in self.skills["localization"].items():
                    for idx, skill in skill_map.items():
                        # 一番最初に合致したスキルとなる(skill tableには同じ名前のスキルがあることも)
                        if "name" in skill and skill["name"] == local_name:
                            SKELETON_DICT["skills"][idx] = {}
                            SKELETON_DICT["skills"][idx]["lv"] = skill_lv
                            remove_localization_list.append(local_name)
                            break

                for local_name in remove_localization_list:
                    del self.skills["localization"][local_name]

                if len(self.skills["localization"]) == 0:
                    del self.skills["localization"]

            for key in self.skills.keys():
                SKELETON_DICT["skills"][key] = self.skills[key]

        if self.equipments is not None:
            for key in self.equipments.keys():
                SKELETON_DICT["equipments"][key] = self.equipments[key]

        if self.items is not None:
            for key in self.items.keys():
                SKELETON_DICT["items"][key] = self.items[key]

        if self.items is not None:
            for key in self.supports.keys():
                SKELETON_DICT["supports"][key] = self.supports[key]

        if self.additional_info is not None:
            if "character_name" in self.additional_info:
                SKELETON_DICT["additional_info"]["character_name"] = self.additional_info["character_name"]
            if "world_name" in self.additional_info:
                SKELETON_DICT["additional_info"]["world_name"] = self.additional_info["world_name"]

            if "hp_base_point" in self.additional_info:
                try:
                    SKELETON_DICT["additional_info"]["hp_base_point"] = int(self.additional_info["hp_base_point"])
                except ValueError:
                    pass
            if "sp_base_point" in self.additional_info:
                try:
                    SKELETON_DICT["additional_info"]["sp_base_point"] = int(self.additional_info["sp_base_point"])
                except ValueError:
                    pass

        return SKELETON_DICT

    def to_json(self, compact: bool = False, ensure_ascii: bool = False, sort_keys: bool = False, indent: int = 0) -> str:
        return json.dumps(self.to_dict(compact=compact), ensure_ascii=ensure_ascii, sort_keys=sort_keys, indent=indent)

@app.get("/")
async def index():
    return templates.TemplateResponse("index.html", {"request": {}})

@app.post("/")
async def translator(request: Request, data: CharacterDataVersion2):
    success: bool = True

    format_version: int|None = None

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
async def rodb_simulator(request: Request, data: CharacterDataVersion2, version: int = 1):
    data_encoded: str = ""
    try:
        # dict => json
        data_json: str = data.to_json(indent=4)

        # json => copressed
        cctx = zstd.ZstdCompressor()
        data_compressed: bytes = cctx.compress(data_json.encode("utf-8"))

        # zstd compressed => encoded
        data_encoded = base64.urlsafe_b64encode(data_compressed).decode("utf-8")

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
async def roratorio_hub(request: Request, data: CharacterDataVersion2, version: int = 4):
    data_encoded: str = ""
    try:
        # dict => json
        data_json: str = data.to_json(indent=4)

        # json => copressed
        cctx = zstd.ZstdCompressor()
        data_compressed: bytes = cctx.compress(data_json.encode("utf-8"))

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
            "url" : f"https://roratorio-hub.github.io/ratorio/ro{version}/m/calcx.html?rtx2:{data_encoded}"
        })

@app.get("/search/skill")
async def search_skill(request: Request, word: str = "", ratorio_skill_num: int|None = None):
    if word == "":
        return JSONResponse({
            "success": False,
            "message": "Please 'word' query."
        })

    skill_map: dict = {}
    try:
        with open(yaml_table["skill"], "r", encoding="utf-8") as fp:
            skill_map = yaml.safe_load(fp)
    except:
        pass

    success: bool = False
    skill_name: str|None = None
    skill_data: dict|None = None
    for idx, job in skill_map.items():
        # 一番最初に合致したスキルとなる(skill tableには同じ名前のスキルがあることも)
        if "name" in job and job["name"] == word:
            success = True
            skill_name = idx
            skill_data = job
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
async def approximate_search_skill(request: Request, word: str = "", ratorio_skill_num: int|None = None):
    if word == "":
        return JSONResponse({
            "success": False,
            "message": "Please 'word' query."
        })

    skill_map: dict = {}
    try:
        with open(yaml_table["skill"], "r", encoding="utf-8") as fp:
            skill_map = yaml.safe_load(fp)
    except:
        pass

    success: bool = False
    skill_name: str|None = None
    skill_data: dict|None = None

    choices: dict = {idx: skill['name'] for idx, skill in skill_map.items() if 'name' in skill}
    # wordと最も近い物を１件だけ抽出
    result = extract(word, choices, limit = 1)

    if len(result) > 0:
        success = True
        skill_name = list(result[0])[2] # type: ignore
        skill_data = skill_map[skill_name]

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
