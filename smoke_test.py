import io
import time

from app import app, create_token, query_one


def auth_headers_for_role(role_name):
    user = query_one(
        """
        SELECT id, username, email, full_name, role, patron_id
        FROM app_users
        WHERE role = %s
        ORDER BY id ASC
        LIMIT 1
        """,
        [role_name],
    )
    if not user:
        raise RuntimeError(f"Не найден пользователь с ролью {role_name}")
    token = create_token(user)
    return {"Authorization": f"Bearer {token}"}, user


def ensure(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    client = app.test_client()
    librarian_headers, librarian_user = auth_headers_for_role("librarian")
    admin_headers, _ = auth_headers_for_role("admin")
    reader_headers, reader_user = auth_headers_for_role("reader")
    manager_user = query_one("SELECT id FROM app_users WHERE LOWER(email) = 'manager@example.com'")
    if not manager_user:
        manager_create = client.post(
            "/api/admin/users",
            headers=admin_headers,
            json={
                "fullName": "Менеджер тестов",
                "email": "manager@example.com",
                "password": "manager123",
                "role": "manager",
                "isActive": True,
            },
        )
        ensure(manager_create.status_code == 201, f"manager create failed: {manager_create.status_code}")
    manager_headers, _ = auth_headers_for_role("manager")

    # 1) Role visibility
    reader_boot = client.get("/api/library/bootstrap", headers=reader_headers)
    ensure(reader_boot.status_code == 200, "bootstrap reader failed")
    reader_data = reader_boot.get_json()
    ensure(reader_data["user"]["role"] == "reader", "reader role mismatch")
    ensure(isinstance(reader_data.get("profile"), dict), "reader profile missing")
    ensure("booksRead" in reader_data["profile"], "profile.booksRead missing")
    ensure("recentRead" in reader_data["profile"], "profile.recentRead missing")
    if reader_user.get("patron_id"):
        patron_profile = client.get(
            f"/api/library/patrons/{reader_user['patron_id']}/profile",
            headers=librarian_headers,
        )
        ensure(patron_profile.status_code == 200, f"patron profile failed: {patron_profile.status_code}")
        ensure(patron_profile.get_json().get("fullName"), "patron profile fullName missing")
    if reader_data["books"]:
        sample = reader_data["books"][0]
        ensure("replacement_cost" not in sample, "reader sees replacement_cost")
        ensure("request_count" not in sample, "reader sees request_count")

    admin_boot = client.get("/api/library/bootstrap", headers=admin_headers)
    ensure(admin_boot.status_code == 200, "bootstrap admin failed")
    admin_data = admin_boot.get_json()
    ensure(isinstance(admin_data.get("requests"), list), "admin requests missing")
    manager_boot = client.get("/api/library/bootstrap", headers=manager_headers)
    ensure(manager_boot.status_code == 200, "bootstrap manager failed")
    manager_data = manager_boot.get_json()
    ensure(manager_data["user"]["role"] == "manager", "manager role mismatch")
    ensure(isinstance(manager_data.get("loans"), list), "manager loans missing in bootstrap")
    ensure(isinstance(manager_data.get("requests"), list), "manager requests missing in bootstrap")

    # 2) Create book + copies
    category = query_one("SELECT id FROM categories ORDER BY id LIMIT 1")
    ensure(category is not None, "categories missing")
    stamp = str(int(time.time()))
    isbn = f"SMOKE-{stamp}"
    create_payload = {
        "categoryId": category["id"],
        "title": f"Smoke Book {stamp}",
        "author": "QA Bot",
        "isbn": isbn,
        "publishYear": 2024,
        "language": "Русский",
        "publisher": "Test",
        "shelfCode": "QA-1",
        "replacementCost": 500,
        "initialCopies": 3,
        "conditionRating": 5,
    }
    created = client.post("/api/library/books", headers=librarian_headers, json=create_payload)
    ensure(created.status_code == 201, f"create book failed: {created.status_code} {created.get_json()}")
    book_id = created.get_json()["id"]

    # 3) Edit book
    upd = create_payload.copy()
    upd["title"] = f"Smoke Book Updated {stamp}"
    updated = client.put(f"/api/library/books/{book_id}", headers=librarian_headers, json=upd)
    ensure(updated.status_code == 200, "update book failed")

    copies = client.get(f"/api/library/books/{book_id}/copies", headers=librarian_headers)
    ensure(copies.status_code == 200, "copies fetch failed")
    copy_rows = copies.get_json()
    ensure(len(copy_rows) >= 3, "not enough copies created")
    admin_copies = client.get(f"/api/library/books/{book_id}/copies", headers=admin_headers)
    ensure(admin_copies.status_code == 200, "admin copies fetch failed")
    manager_copies = client.get(f"/api/library/books/{book_id}/copies", headers=manager_headers)
    ensure(manager_copies.status_code == 403, "manager must not list book copies")
    reader_copies = client.get(f"/api/library/books/{book_id}/copies", headers=reader_headers)
    ensure(reader_copies.status_code == 403, "reader must not list book copies")

    # 4) Replace once should work, second replace same copy should fail
    replace_target = copy_rows[0]["id"]
    rep1 = client.post(f"/api/library/copies/{replace_target}/replace", headers=librarian_headers, json={})
    ensure(rep1.status_code == 204, f"first replace failed: {rep1.status_code}")
    rep2 = client.post(f"/api/library/copies/{replace_target}/replace", headers=librarian_headers, json={})
    ensure(rep2.status_code == 400, f"second replace expected 400, got {rep2.status_code}")
    edit_target = copy_rows[1]["id"]
    edit_resp = client.put(
        f"/api/library/copies/{edit_target}",
        headers=librarian_headers,
        json={
            "conditionRating": 3,
            "status": "damaged",
            "acquisitionDate": "2020-01-15",
            "notes": "Проверка редактирования",
        },
    )
    ensure(edit_resp.status_code == 204, f"copy edit failed: {edit_resp.status_code}")
    edited = client.get(f"/api/library/books/{book_id}/copies", headers=librarian_headers).get_json()
    edited_row = next(c for c in edited if c["id"] == edit_target)
    ensure(edited_row["condition_rating"] == 3, "copy condition not updated")
    ensure(edited_row["status"] == "damaged", "copy status not updated")

    # refresh copies after replacement
    copy_rows = client.get(f"/api/library/books/{book_id}/copies", headers=librarian_headers).get_json()
    available = [c for c in copy_rows if c["status"] == "available"]
    ensure(len(available) >= 2, "available copies missing for loan tests")

    patron_id = reader_user.get("patron_id")
    ensure(patron_id is not None, "reader has no patron_id")

    # 5) Issue -> renew -> return
    loan_copy_1 = available[0]["id"]
    issue_1 = client.post(
        "/api/library/loans/issue",
        headers=manager_headers,
        json={"copyId": loan_copy_1, "patronId": patron_id, "dueAt": "2030-01-10", "notes": "smoke issue"},
    )
    ensure(issue_1.status_code == 204, "issue_1 failed")
    loan1 = query_one(
        "SELECT id FROM loans WHERE copy_id = %s AND status IN ('active','renewed','overdue') ORDER BY id DESC LIMIT 1",
        [loan_copy_1],
    )
    ensure(loan1 is not None, "loan1 not found")
    renew = client.post(f"/api/library/loans/{loan1['id']}/renew", headers=manager_headers, json={"dueAt": "2030-02-10"})
    ensure(renew.status_code == 204, "renew by manager failed")
    ret = client.post(
        f"/api/library/loans/{loan1['id']}/return",
        headers=manager_headers,
        json={"copyStatus": "available", "conditionRating": 5},
    )
    ensure(ret.status_code == 204, "return failed")

    # 6) Issue -> lost
    loan_copy_2 = available[1]["id"]
    issue_2 = client.post(
        "/api/library/loans/issue",
        headers=manager_headers,
        json={"copyId": loan_copy_2, "patronId": patron_id, "dueAt": "2030-01-10", "notes": "smoke issue 2"},
    )
    ensure(issue_2.status_code == 204, "issue_2 failed")
    loan2 = query_one(
        "SELECT id FROM loans WHERE copy_id = %s AND status IN ('active','renewed','overdue') ORDER BY id DESC LIMIT 1",
        [loan_copy_2],
    )
    ensure(loan2 is not None, "loan2 not found")
    lost = client.post(f"/api/library/loans/{loan2['id']}/lost", headers=manager_headers, json={"notes": "smoke lost"})
    ensure(lost.status_code == 204, "lost failed")

    # 7) Reader renew request flow
    remaining_available = [c for c in client.get(f"/api/library/books/{book_id}/copies", headers=librarian_headers).get_json() if c["status"] == "available"]
    ensure(remaining_available, "no copy left for reader renew-request test")
    loan_copy_3 = remaining_available[0]["id"]
    issue_3 = client.post(
        "/api/library/loans/issue",
        headers=manager_headers,
        json={"copyId": loan_copy_3, "patronId": patron_id, "dueAt": "2030-01-10", "notes": "smoke issue 3"},
    )
    ensure(issue_3.status_code == 204, "issue_3 failed")
    loan3 = query_one(
        "SELECT id FROM loans WHERE copy_id = %s AND status IN ('active','renewed','overdue') ORDER BY id DESC LIMIT 1",
        [loan_copy_3],
    )
    ensure(loan3 is not None, "loan3 not found")
    rr = client.post(f"/api/library/loans/{loan3['id']}/renew-request", headers=reader_headers, json={})
    ensure(rr.status_code == 200, f"reader renew-request failed: {rr.status_code}")

    # 8) Inter-role flow: reader creates request, admin approves
    returned_for_request = client.post(
        f"/api/library/loans/{loan3['id']}/return",
        headers=librarian_headers,
        json={"copyStatus": "available", "conditionRating": 5},
    )
    ensure(returned_for_request.status_code == 204, "return before request failed")
    req_create = client.post("/api/library/requests", headers=reader_headers, json={"bookId": book_id})
    ensure(req_create.status_code == 201, f"request create failed: {req_create.status_code}")
    request_id = req_create.get_json()["id"]
    approve = client.post(
        f"/api/library/requests/{request_id}/approve",
        headers=admin_headers,
        json={"dueAt": "2030-03-15"},
    )
    ensure(approve.status_code == 204, f"admin approve failed: {approve.status_code}")

    # 9) Staff can load requests endpoint too
    staff_req = client.get("/api/library/requests", headers=librarian_headers)
    ensure(staff_req.status_code == 200, "librarian /requests should be allowed")
    manager_req = client.get("/api/library/requests", headers=manager_headers)
    ensure(manager_req.status_code == 200, "manager /requests should be allowed")

    # 10) Forgot / reset password (reader, demo link)
    reader_email = reader_user.get("email") or reader_user.get("username")
    forgot = client.post("/api/auth/forgot-password", json={"email": reader_email})
    ensure(forgot.status_code == 200, f"forgot-password failed: {forgot.status_code}")
    forgot_data = forgot.get_json()
    ensure(forgot_data.get("resetUrl"), "demo resetUrl missing")
    token = forgot_data["resetUrl"].split("reset=")[-1]
    reset_pw = client.post(
        "/api/auth/reset-password",
        json={"token": token, "newPassword": "reader123"},
    )
    ensure(reset_pw.status_code == 200, f"reset-password failed: {reset_pw.status_code}")

    # 11) Public home banners + admin catalog CSV
    banners = client.get("/api/public/home-banners")
    ensure(banners.status_code == 200, "home-banners failed")
    ensure(isinstance(banners.get_json(), list), "home-banners should return list")

    template = client.get("/api/admin/catalog/template", headers=admin_headers)
    ensure(template.status_code == 200, f"catalog template failed: {template.status_code}")
    ensure("text/csv" in (template.content_type or ""), "catalog template not csv")

    export = client.get("/api/admin/catalog/export", headers=admin_headers)
    ensure(export.status_code == 200, f"catalog export failed: {export.status_code}")
    ensure(b"title;author;isbn" in export.data, "catalog export header missing")

    reader_template = client.get("/api/admin/catalog/template", headers=reader_headers)
    ensure(reader_template.status_code == 403, "reader must not download catalog template")

    health = client.get("/api/health")
    ensure(health.status_code == 200, "health check failed")
    ensure(health.get_json().get("ok") is True, "health payload invalid")

    index = client.get("/")
    ensure(index.status_code == 200, "index page failed")
    ensure(b"layout.js" in index.data, "index missing layout.js")

    partial = client.get("/partials/main.html")
    ensure(partial.status_code == 200, "main partial failed")
    ensure(b"copiesBackToListButton" in partial.data, "copies back button missing in partial")
    ensure(b"changeCopiesBookButton" in partial.data, "change book button missing in partial")

    import_csv = (
        "title;author;isbn;category;language;publish_year;publisher;shelf_code;description;replacement_cost;cover_image;initial_copies\n"
        f"Import Smoke {stamp};Import Author;ISBN-IMP-{stamp};Художественная литература;Русский;2021;Test;IMP-1;Imported;400;;1\n"
    )
    imported = client.post(
        "/api/admin/catalog/import",
        headers=admin_headers,
        data={"file": (io.BytesIO(import_csv.encode("utf-8-sig")), "import.csv")},
        content_type="multipart/form-data",
    )
    ensure(imported.status_code == 200, f"catalog import failed: {imported.status_code} {imported.get_json()}")
    import_data = imported.get_json()
    ensure(import_data.get("created", 0) >= 1, "catalog import created no books")
    imported_book = query_one("SELECT id FROM books WHERE isbn = %s", [f"ISBN-IMP-{stamp}"])
    ensure(imported_book is not None, "imported book missing in db")
    client.delete(f"/api/library/books/{imported_book['id']}", headers=librarian_headers)

    # cleanup
    client.delete(f"/api/library/books/{book_id}", headers=librarian_headers)

    print("SMOKE TESTS PASSED")
    print(f"Tested by librarian: {librarian_user['email']}")


if __name__ == "__main__":
    main()
