"""
Centralized selector registry for the portal RPA bot.

═══════════════════════════════════════════════════════════════════
SELECTOR STATUS — READ BEFORE EDITING
═══════════════════════════════════════════════════════════════════
Every locator in this file is a PLACEHOLDER.
They are educated guesses based on common portal patterns.
NONE have been verified against the real DOM.

How to verify a selector:
  1. Open the portal in Chrome with DevTools (F12).
  2. Find the element using the Elements panel or the Inspector.
  3. Right-click → Copy → Copy XPath (or Copy selector).
  4. Replace the placeholder value below.
  5. Remove the TODO comment and add:  # VERIFIED: YYYY-MM-DD

Locator format: (By.Strategy, "value")
  — identical to the first two arguments of driver.find_element()
  — passed directly to WebDriverWait(...).until(EC.presence_of_element_located(locator))
═══════════════════════════════════════════════════════════════════
"""

from selenium.webdriver.common.by import By

# ── Login page ────────────────────────────────────────────────────────────────


class LoginPage:
    # TODO: verify — text input for the portal username / email
    USERNAME = (By.ID, "username")

    # TODO: verify — password input
    PASSWORD = (By.ID, "password")

    # VERIFIED: Aquila's login submit button uses id="_submit"
    SUBMIT_BUTTON = (By.ID, "_submit")

    # VERIFIED: Aquila renders id="hir_logo" only after a successful login/redirect.
    POST_LOGIN_INDICATOR = (By.ID, "hir_logo")

    # TODO: verify — error banner/alert shown when credentials are wrong
    # Used to distinguish a "wrong password" failure from a generic timeout.
    # If the portal does not show an explicit error, set to None and remove
    # the related check in login.py.
    LOGIN_ERROR_MESSAGE = (
        By.XPATH,
        "//*[contains(@class,'alert-danger') or contains(@class,'login-error')]",
    )


# ── Headquarter selection (post-login, before navigation) ────────────────────
# VERIFIED from real DOM (PDX project): after login Aquila shows a "Cambio de sede"
# option.  The dropdown id is "change_headquarter".


class HeadquarterSelect:
    # VERIFIED: span that triggers the "Cambio de sede" dialog.
    CAMBIO_SEDE_TRIGGER = (By.XPATH, "//span[normalize-space(text())='Cambio de sede']")

    # VERIFIED: the <select> dropdown rendered inside the dialog.
    DROPDOWN = (By.ID, "change_headquarter")

    # The sede text to select — must match exactly the option text in the dropdown.
    SEDE_NAME = "Prodiagnostico Sede Poblado"


# ── Main navigation ───────────────────────────────────────────────────────────


class MainNav:
    # VERIFIED from real DOM:
    # <a href="#" class="ui-button ui-widget ui-menubar-link ..."
    #    role="menuitem" aria-haspopup="true">
    #   <span class="ui-button-text">Facturación</span>
    # </a>
    # Targets the <a> that carries role="menuitem" and whose ui-button-text
    # span contains "Facturación".
    FACTURACION_MENU = (
        By.XPATH,
        "//a[@role='menuitem' and .//span[@class='ui-button-text' and normalize-space(text())='Facturación']]",
    )

    # Fallback: same pattern but only requires the span text, ignoring role.
    FACTURACION_MENU_FALLBACK = (
        By.XPATH,
        "//span[@class='ui-button-text' and normalize-space(text())='Facturación']/parent::a",
    )

    # VERIFIED from real DOM:
    # <a href="/facturacion/facturacion/consulta_ordenes_facturar"
    #    id="ui-id-73" class="ui-corner-all" tabindex="-1" role="menuitem">
    #   Generar facturas
    # </a>
    # Primary: use href — immune to text or class changes.
    GENERAR_FACTURA_ITEM = (
        By.XPATH,
        "//a[@href='/facturacion/facturacion/consulta_ordenes_facturar']",
    )

    # Fallback: role=menuitem + exact text (note lowercase 'f' and plural).
    GENERAR_FACTURA_ITEM_FALLBACK = (
        By.XPATH,
        "//a[@role='menuitem' and normalize-space(text())='Generar facturas']",
    )

    # Page-ready: URL must contain this path segment (checked via EC.url_contains).
    # This constant is kept for reference; navigation.py uses EC.url_contains directly.
    GENERAR_FACTURA_PAGE_READY_PATH = "consulta_ordenes_facturar"


# ── Generar Factura — filter form ─────────────────────────────────────────────


class FilterForm:
    # VERIFIED from real DOM:
    FECHA_INICIAL = (By.ID, "dateInit")
    FECHA_FINAL = (By.ID, "dateEnd")

    # VERIFIED from PDX project (fill_order_query_form.py):
    # Bootstrap Select dropdowns — each trigger is a <button data-id="...">.
    # Selection order matters: Convenio → Contrato (unlocked by Convenio AJAX)
    #   → Sedes (unlocked by Contrato AJAX) → Modalidad → dates → Buscar.

    # Convenio / régimen dropdown.
    CONVENIOS_TRIGGER = (By.CSS_SELECTOR, "button[data-id='convenios_facturas']")

    # Contrato dropdown — initially DISABLED; becomes enabled after Convenio.
    CONTRATOS_TRIGGER = (By.CSS_SELECTOR, "button[data-id='contratos_facturas']")

    # Sedes dropdown — initially DISABLED; becomes enabled after Contrato.
    SEDES_TRIGGER = (By.CSS_SELECTOR, "button[data-id='sedes_facturas']")

    # Modalidad dropdown.
    MODALIDADES_TRIGGER = (By.CSS_SELECTOR, "button[data-id='modalidades']")

    # "Select All" button inside any open Bootstrap Select dropdown.
    # VERIFIED: class includes "bs-select-all"
    SELECT_ALL_BUTTON = (By.CSS_SELECTOR, ".dropdown-menu.open .bs-select-all")

    # BlockUI overlay that appears while AJAX loads new dropdown options.
    BLOCKUI_OVERLAY = (By.CSS_SELECTOR, "div.blockUI.blockOverlay")

    # VERIFIED from real DOM:
    BUSCAR_BUTTON = (By.ID, "buscar")


# ── Generar Factura — results table ───────────────────────────────────────────


class ResultTable:
    # VERIFIED from real DOM:
    # <table id="detalle_consulta" class="table ... dataTable ...">
    CONTAINER = (By.ID, "detalle_consulta")

    # Data rows only — excludes:
    #   (a) the DataTables "empty" placeholder row (class dataTables_empty)
    #   (b) DataTables child/detail rows that DataTables inserts when a row is
    #       expanded (class "child").  Those rows have a completely different
    #       DOM structure and must not be treated as regular data rows.
    # VERIFIED: empty state text is "Tabla sin información".
    BODY_ROWS = (
        By.XPATH,
        "//table[@id='detalle_consulta']//tbody/tr["
        "not(td[contains(@class,'dataTables_empty')]) and "
        "not(contains(@class,'child'))"
        "]",
    )

    # VERIFIED: DataTables empty-state cell text.
    NO_RESULTS_MESSAGE = (
        By.CSS_SELECTOR,
        "#detalle_consulta tbody td.dataTables_empty",
    )

    # DataTables info row — shows "Showing X to Y of Z entries".
    # Used as a reliable "search completed" signal regardless of row count.
    DATATABLES_INFO = (By.CSS_SELECTOR, "#detalle_consulta_info")


# ── Column mapping ────────────────────────────────────────────────────────────
# VERIFIED from real DOM (table id="detalle_consulta").
# 0-based index of each <td> in a data row.
# Visible columns (0-7):  Fecha cita, Fecha asistencial, No. Orden,
#   Código factura, No facturar, Listo para facturar, Auditar,
#   Código de autorización.
# Hidden columns (display:none in <th>, but present as <td> in rows):
#   8=Documento, 9=Nombres, 10=Orden escaneada, 11=Detalle,
#   12=Modalidad, 13=Cups, 14=Estudios, 15=Procedencia,
#   16=Sede, 17=Accession Number, 18=Estado.


class ColumnIndex:
    # "No. Orden" — the portal's own order/invoice identifier.
    EXTERNAL_ROW_ID: int | None = 2

    # "Nombres" — patient full name (hidden column, present in DOM).
    PATIENT_NAME: int | None = 9

    # "Documento" — patient national ID (hidden column, present in DOM).
    PATIENT_DOCUMENT: int | None = 8

    # "Fecha asistencial" — date the service was rendered (col_0).
    # col_0 is the service date and is always populated.
    # col_1 is the billing/facturation date and is often empty.
    # Aquila renders dates as "YYYY-MM-DD HH:MM:SS", sometimes comma-separated
    # when an order covers multiple days.  Extractor normalises to "YYYY-MM-DD".
    DATE_SERVICE_OR_FACTURATION: int | None = 0

    # "Sede" — clinic/site name (hidden column, present in DOM).
    SITE: int | None = 16

    # "Cups" — CUPS code(s) for the service (hidden column).
    CUPS: int | None = 13

    # "Modalidad" — modality code, e.g. "CR", "MG" (hidden column).
    MODALITY: int | None = 12

    # "Estado" — row status from Aquila, e.g. "VALIDADO" (hidden column).
    STATUS: int | None = 18

    # "Código de autorización" — VISIBLE column (index 7) but rendered as a
    # hidden <input class="codigoAut" value="..."> inside the cell, NOT as
    # visible text.  cells[7].text returns "".  Must use
    # row.find_elements(By.CLASS_NAME, "codigoAut")[0].get_attribute("value").
    AUTHORIZATION_CODE_INPUT_CLASS: str = "codigoAut"

    # "Contrato" — contract code for the sede, e.g. "RNG49858" (col_17).
    # VERIFIED from raw_row_json: col_17 contains the contract code.
    CONTRACT: int | None = 17


# ── Date format ───────────────────────────────────────────────────────────────

# VERIFIED from PDX project (fill_order_query_form.py — set_date_range):
# Aquila's dateInit/dateEnd inputs accept ISO format YYYY-MM-DD.
PORTAL_DATE_FORMAT = "%Y-%m-%d"
