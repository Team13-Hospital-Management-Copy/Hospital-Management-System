import time

from app.models import Patient
from app.roles import ADMINISTRATOR, DOCTOR, RECEPTIONIST

PATIENTS_URL = "/patients/"
SEARCH_URL = "/patients/search"


def patient_payload(**overrides):
    data = {
        "full_name": "Test Patient",
        "age": 30,
        "gender": "Female",
        "phone": "9876543210",
        "address": "Test Address",
    }
    data.update(overrides)
    return data


def register(client, headers, **overrides) -> dict:
    response = client.post(PATIENTS_URL, json=patient_payload(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(seed_user, login_token, role=RECEPTIONIST, username="staff1"):
    seed_user(username=username, role=role)
    return {"Authorization": f"Bearer {login_token(username)}"}


def test_search_by_uhid_returns_the_correct_patient(client, seed_user, login_token, receptionist_header):
    headers = auth_headers(seed_user, login_token)
    target = register(client, receptionist_header, full_name="Asha Rao", phone="9000000001")
    register(client, receptionist_header, full_name="Bina Rao", phone="9000000002")

    response = client.get(SEARCH_URL, params={"uhid": target["uhid"]}, headers=headers)

    assert response.status_code == 200
    assert [p["uhid"] for p in response.json()] == [target["uhid"]]


def test_search_by_name_returns_the_correct_patient(client, seed_user, login_token, receptionist_header):
    headers = auth_headers(seed_user, login_token)
    target = register(client, receptionist_header, full_name="Meera Iyer", phone="9000000003")
    register(client, receptionist_header, full_name="Ravi Kumar", phone="9000000004")

    response = client.get(SEARCH_URL, params={"name": "Meera Iyer"}, headers=headers)

    assert response.status_code == 200
    assert [p["uhid"] for p in response.json()] == [target["uhid"]]


def test_search_by_phone_returns_the_correct_patient(client, seed_user, login_token, receptionist_header):
    headers = auth_headers(seed_user, login_token)
    target = register(client, receptionist_header, full_name="Dev Sharma", phone="9123456780")
    register(client, receptionist_header, full_name="Esha Sharma", phone="9111111111")

    response = client.get(SEARCH_URL, params={"phone": "9123456780"}, headers=headers)

    assert response.status_code == 200
    assert [p["uhid"] for p in response.json()] == [target["uhid"]]


def test_name_search_supports_partial_and_case_insensitive_matches(
    client, seed_user, login_token, receptionist_header
):
    headers = auth_headers(seed_user, login_token)
    target = register(client, receptionist_header, full_name="Lakshmi Narayan", phone="9000000005")
    register(client, receptionist_header, full_name="Gopal Das", phone="9000000006")

    response = client.get(SEARCH_URL, params={"name": "  LAKSH "}, headers=headers)

    assert response.status_code == 200
    assert [p["uhid"] for p in response.json()] == [target["uhid"]]


def test_phone_search_supports_partial_matches(client, seed_user, login_token, receptionist_header):
    headers = auth_headers(seed_user, login_token)
    target = register(client, receptionist_header, full_name="Farah Khan", phone="9988776655")
    register(client, receptionist_header, full_name="Gita Menon", phone="9000000007")

    response = client.get(SEARCH_URL, params={"phone": "8776"}, headers=headers)

    assert response.status_code == 200
    assert [p["uhid"] for p in response.json()] == [target["uhid"]]


def test_uhid_search_supports_partial_matches(client, seed_user, login_token, receptionist_header):
    headers = auth_headers(seed_user, login_token)
    first = register(client, receptionist_header, full_name="Hari Pillai", phone="9000000008")
    register(client, receptionist_header, full_name="Isha Nair", phone="9000000009")

    response = client.get(SEARCH_URL, params={"uhid": first["uhid"][-4:]}, headers=headers)

    assert response.status_code == 200
    assert [p["uhid"] for p in response.json()] == [first["uhid"]]


def test_multiple_matching_patients_are_all_returned_in_uhid_order(
    client, seed_user, login_token, receptionist_header
):
    headers = auth_headers(seed_user, login_token)
    first = register(client, receptionist_header, full_name="Kiran Mehta", phone="9000000010")
    second = register(client, receptionist_header, full_name="Kiran Joshi", phone="9000000011")
    register(client, receptionist_header, full_name="Lata Pandey", phone="9000000012")

    response = client.get(SEARCH_URL, params={"name": "kiran"}, headers=headers)

    assert response.status_code == 200
    assert [p["uhid"] for p in response.json()] == sorted([first["uhid"], second["uhid"]])


def test_search_result_contains_the_patient_fields(client, seed_user, login_token, receptionist_header):
    headers = auth_headers(seed_user, login_token)
    created = register(client, receptionist_header, full_name="Mohan Das", age=45, gender="Male", phone="9000000013")

    response = client.get(SEARCH_URL, params={"uhid": created["uhid"]}, headers=headers)

    assert response.status_code == 200
    (patient,) = response.json()
    assert set(patient) == {"id", "uhid", "full_name", "age", "gender", "phone", "email", "address"}
    assert patient["full_name"] == "Mohan Das"
    assert patient["age"] == 45
    assert patient["gender"] == "Male"
    assert patient["phone"] == "9000000013"


def test_no_matching_patient_returns_empty_list(client, seed_user, login_token, receptionist_header):
    headers = auth_headers(seed_user, login_token)
    register(client, receptionist_header, full_name="Nina Roy", phone="9000000014")

    response = client.get(SEARCH_URL, params={"name": "Nonexistent"}, headers=headers)

    assert response.status_code == 200
    assert response.json() == []


def test_wildcard_characters_in_input_are_matched_literally(
    client, seed_user, login_token, receptionist_header
):
    headers = auth_headers(seed_user, login_token)
    register(client, receptionist_header, full_name="Omar Ali", phone="9000000015")

    percent = client.get(SEARCH_URL, params={"name": "%"}, headers=headers)
    underscore = client.get(SEARCH_URL, params={"name": "_"}, headers=headers)

    assert percent.status_code == 200
    assert percent.json() == []
    assert underscore.status_code == 200
    assert underscore.json() == []


def test_search_returns_at_most_the_search_limit(
    client, seed_user, login_token, db_session, receptionist_header
):
    headers = auth_headers(seed_user, login_token)
    for index in range(55):
        register(client, receptionist_header, full_name=f"Common Name {index}", phone=f"90000{index:05d}")

    response = client.get(SEARCH_URL, params={"name": "Common"}, headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 50


def test_search_over_a_larger_dataset_completes_within_two_seconds(
    client, seed_user, login_token, db_session
):
    headers = auth_headers(seed_user, login_token)
    db_session.add_all(
        Patient(
            uhid=f"HMS-{index:06d}",
            full_name=f"Bulk Patient {index}",
            age=40,
            gender="Male",
            phone=f"8{index:09d}",
            address="",
        )
        for index in range(1, 501)
    )
    db_session.commit()

    started = time.perf_counter()
    response = client.get(SEARCH_URL, params={"phone": "8000000250"}, headers=headers)
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert [p["uhid"] for p in response.json()] == ["HMS-000250"]
    assert elapsed < 2


def test_search_without_any_key_returns_422(client, seed_user, login_token):
    headers = auth_headers(seed_user, login_token)

    response = client.get(SEARCH_URL, headers=headers)

    assert response.status_code == 422
    assert response.json()["detail"] == "Provide exactly one of uhid, name or phone."


def test_search_with_more_than_one_key_returns_422(client, seed_user, login_token):
    headers = auth_headers(seed_user, login_token)

    response = client.get(SEARCH_URL, params={"name": "Asha", "phone": "9000"}, headers=headers)

    assert response.status_code == 422


def test_blank_search_value_returns_422(client, seed_user, login_token):
    headers = auth_headers(seed_user, login_token)

    response = client.get(SEARCH_URL, params={"name": "   "}, headers=headers)

    assert response.status_code == 422
    assert response.json()["detail"] == "Search value cannot be empty."


def test_overlong_search_value_returns_422(client, seed_user, login_token):
    headers = auth_headers(seed_user, login_token)

    response = client.get(SEARCH_URL, params={"name": "a" * 151}, headers=headers)

    assert response.status_code == 422


def test_search_requires_authentication(client, seed_user):
    seed_user(username="staff2", role=RECEPTIONIST)

    response = client.get(SEARCH_URL, params={"name": "Anyone"})

    assert response.status_code == 401


def test_search_is_allowed_for_doctors(client, seed_user, login_token, receptionist_header):
    headers = auth_headers(seed_user, login_token, role=DOCTOR, username="doctor1")
    target = register(client, receptionist_header, full_name="Pooja Varma", phone="9000000016")

    response = client.get(SEARCH_URL, params={"uhid": target["uhid"]}, headers=headers)

    assert response.status_code == 200
    assert [p["uhid"] for p in response.json()] == [target["uhid"]]


def test_search_is_denied_for_roles_outside_the_permitted_scope(client, seed_user, login_token):
    headers = auth_headers(seed_user, login_token, role=ADMINISTRATOR, username="admin1")

    response = client.get(SEARCH_URL, params={"name": "Anyone"}, headers=headers)

    assert response.status_code == 403


def test_search_declares_bearer_auth_so_docs_can_send_the_token(client):
    schema = client.get("/openapi.json").json()

    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    assert {"HTTPBearer": []} in schema["paths"]["/patients/search"]["get"]["security"]


def test_uhid_retrieval_still_works_after_search_is_added(client, receptionist_header):
    created = register(client, receptionist_header, full_name="Quinn Fernandes", phone="9000000017")

    response = client.get(f"/patients/{created['uhid']}", headers=receptionist_header)

    assert response.status_code == 200
    assert response.json()["uhid"] == created["uhid"]
    assert response.json()["full_name"] == "Quinn Fernandes"
