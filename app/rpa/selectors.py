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

    # TODO: verify — the primary submit / login button
    SUBMIT_BUTTON = (By.XPATH, "//button[@type='submit']")

    # TODO: verify — any element that is ONLY present once the user is logged in
    # Good candidates: a user avatar, the main navigation bar, or a dashboard heading.
    # This is used as the "login succeeded" signal after clicking Submit.
    POST_LOGIN_INDICATOR = (By.XPATH, "//nav[contains(@class,'main-nav')]")

    # TODO: verify — error banner/alert shown when credentials are wrong
    # Used to distinguish a "wrong password" failure from a generic timeout.
    # If the portal does not show an explicit error, set to None and remove
    # the related check in login.py.
    LOGIN_ERROR_MESSAGE = (
        By.XPATH,
        "//*[contains(@class,'alert-danger') or contains(@class,'login-error')]",
    )


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

    # Page-ready: the URL will have changed to .../consulta_ordenes_facturar.
    # Match any visible filter-form element that appears after the page loads.
    # TODO: replace with a specific element once the page DOM is known.
    GENERAR_FACTURA_PAGE_READY = (
        By.XPATH,
        "//*[contains(normalize-space(.), 'Fecha Inicial') "
        "or contains(normalize-space(.), 'Fecha Fin') "
        "or contains(normalize-space(.), 'Buscar') "
        "or contains(normalize-space(.), 'Consulta')]",
    )


# ── Generar Factura — filter form ─────────────────────────────────────────────


class FilterForm:
    # VERIFIED from real DOM:
    # <input name="dateInit" id="dateInit"
    #        class="form-control datepicker cor hasDatepicker"
    #        placeholder="Fecha inicial" autocomplete="off">
    FECHA_INICIAL = (By.ID, "dateInit")

    # VERIFIED from real DOM:
    # <input name="dateEnd" id="dateEnd"
    #        class="form-control datepicker cor hasDatepicker"
    #        placeholder="Fecha final" autocomplete="off">
    FECHA_FINAL = (By.ID, "dateEnd")

    # VERIFIED from real DOM:
    # Contratos: data-id="contratos_facturas" — DISABLED by the portal
    # (the logged-in user's contract is fixed; interaction must be skipped).
    # Sedes: trigger identified by title="Sedes" — enabled, has "Select All".

    # Contratos trigger — kept for disabled-check only; do NOT click.
    CONTRATOS_TRIGGER = (By.CSS_SELECTOR, "button[data-id='contratos_facturas']")

    # Sedes trigger button.
    # TODO: confirm data-id once inspected; fallback uses title attribute.
    SEDES_TRIGGER = (
        By.XPATH,
        "//button[@title='Sedes' or .//span[contains(@class,'filter-option') "
        "and normalize-space(text())='Sedes']]",
    )

    # "Select All" button inside any open Bootstrap Select dropdown.
    # VERIFIED: class="actions-btn bs-select-all btn btn-default"
    SELECT_ALL_BUTTON = (By.CSS_SELECTOR, ".dropdown-menu.open .bs-select-all")

    # VERIFIED from real DOM:
    # <button class="btn btn-info form-control" id="buscar"
    #         onclick="BuscarOrden()">Buscar</button>
    BUSCAR_BUTTON = (By.ID, "buscar")


# ── Generar Factura — results table ───────────────────────────────────────────


class ResultTable:
    # VERIFIED from real DOM:
    # <table id="detalle_consulta" class="table ... dataTable ...">
    CONTAINER = (By.ID, "detalle_consulta")

    # Data rows only — excludes the DataTables "empty" placeholder row.
    # VERIFIED: empty state uses <td class="dataTables_empty">Tabla sin información</td>
    BODY_ROWS = (
        By.XPATH,
        "//table[@id='detalle_consulta']//tbody/tr[not(td[contains(@class,'dataTables_empty')])]",
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

    # "Fecha asistencial" — date the service was rendered.
    DATE_SERVICE_OR_FACTURATION: int | None = 1

    # "Sede" — clinic/site name (hidden column, present in DOM).
    SITE: int | None = 16

    # Contract is not a separate column; it comes from the Contratos filter
    # (pre-selected, disabled). Leave None — extractor will skip it.
    CONTRACT: int | None = None


# ── Date format ───────────────────────────────────────────────────────────────

# TODO: verify — format string used when typing dates into FilterForm inputs.
# Check the portal's placeholder text (e.g. "dd/mm/aaaa") or inspect the
# network request sent when a date is selected.
# Common values: "%d/%m/%Y"  "%Y-%m-%d"  "%m/%d/%Y"
PORTAL_DATE_FORMAT = "%d/%m/%Y"
