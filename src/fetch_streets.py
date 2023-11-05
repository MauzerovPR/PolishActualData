import os

import requests
import json
from logging import info
import html.parser as htmlparser
import re


class HTMLParser(htmlparser.HTMLParser):
    scripts: list[str] = []
    __is_reading_script: bool = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.scripts.append("")
            self.__is_reading_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.__is_reading_script = False

    def handle_data(self, data: str) -> None:
        if self.__is_reading_script:
            self.scripts[-1] += data


def main():
    with requests.Session() as session:
        website = session.get("https://wyszukiwarkaregon.stat.gov.pl/appBIR/index.aspx")
        info(f"Status code: {website.status_code}")

        parser = HTMLParser()
        parser.feed(website.text)
        last_script_content = parser.scripts[-1]
        parser.close()

        last_script_content = last_script_content.split(";")[0]

        private_key = "".join([chr(int(char)) for char in re.findall(r"\d+", last_script_content)]).removeprefix("_kluczuzytkownika=")[1:-1]

        del last_script_content, parser, website

        session_id_response = session.post(
            "https://wyszukiwarkaregon.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc/ajaxEndpoint/Zaloguj",
            json={
                "pKluczUzytkownika": private_key,
            },
        )

        headers = {
            'sid': json.loads(session_id_response.text)["d"],
        }

        del session_id_response
        info(f"Session ID: {headers['sid']}")

        provinces_response = session.post(
            "https://wyszukiwarkaregon.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc/ajaxEndpoint/GetWojewodztwa",
            headers=headers,
        )
        provinces = json.loads(json.loads(provinces_response.text)["d"])
        info(f"Provinces: {len(provinces)}")

        all_cities = set()

        for province in provinces[0:]:
            province_id, province_name = province["Kod"], province["Nazwa"]

            sub_provinces = json.loads(json.loads(session.post(
                "https://wyszukiwarkaregon.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc/ajaxEndpoint/GetPowiaty",
                headers=headers,
                json={"pKodWojewodztwa": province_id},
            ).text)["d"] or "[]")

            for sub_province in sub_provinces:
                sub_province_id, sub_province_name = sub_province["KodPowiatu"], sub_province["Powiat"]

                municipalities = json.loads(json.loads(session.post(
                    "https://wyszukiwarkaregon.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc/ajaxEndpoint/GetGminy",
                    headers=headers,
                    json={"pKodPowiatu": sub_province_id, "pKodWojewodztwa": province_id},
                ).text)["d"] or "[]")

                for municipality in municipalities:
                    municipality_id, municipality_name = municipality["KodGminy3"], municipality["Gmina"]

                    cities = json.loads(json.loads(session.post(
                        "https://wyszukiwarkaregon.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc/ajaxEndpoint/GetMiejscowosci",
                        headers=headers,
                        json={"pKodGminy": municipality_id, "pKodPowiatu": sub_province_id, "pKodWojewodztwa": province_id},
                    ).text)["d"] or "[]")

                    for city in cities:
                        city_id, city_name = city["KodStatystyczny"], city["Miejscowosc"]
                        if not os.path.exists(f"data/adresses/province/{province_name}"):
                            os.mkdir(f"data/adresses/province/{province_name}")

                        streets = json.loads(json.loads(session.post(
                            "https://wyszukiwarkaregon.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc/ajaxEndpoint/GetUlice",
                            headers=headers,
                            json={"pKodMiejscowosci": city_id},
                        ).text)["d"] or '[]')

                        if not streets:
                            continue
                        with open(
                                f"data/adresses/province/{province_name}/{city_name}.txt",
                                "a+" if city_name in all_cities else "w+",
                                encoding="UTF-8"
                        ) as f:
                            all_cities.add(city_name)
                            for street in streets:
                                street_id, street_name = street["Symbol"], street["Nazwa1"]
                                f.write(f"{street_name}\n")


if __name__ == '__main__':
    main()
