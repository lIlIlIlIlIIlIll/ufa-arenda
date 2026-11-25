CREATE TABLE IF NOT EXISTS districts (
    district_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    avg_price_sqm DECIMAL(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS owners (
    owner_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name VARCHAR(150) NOT NULL,
    phone VARCHAR(25) NOT NULL,
    passport_data VARCHAR(100) NOT NULL,
    egrn_number VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS realtors (
    realtor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name VARCHAR(150) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'Риелтор',
    phone VARCHAR(25) NOT NULL,
    login VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS properties (
    property_id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    district_id INTEGER NOT NULL,
    property_type VARCHAR(50) NOT NULL DEFAULT 'Квартира',
    address_ufa VARCHAR(255) NOT NULL,
    rooms_count INTEGER NOT NULL,
    area_total DECIMAL(6, 2) NOT NULL,
    floor_info VARCHAR(20) NOT NULL,
    price_monthly DECIMAL(10, 2) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Активен',
    description TEXT,
    FOREIGN KEY (owner_id) REFERENCES owners(owner_id),
    FOREIGN KEY (district_id) REFERENCES districts(district_id)
);

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name VARCHAR(150) NOT NULL,
    phone VARCHAR(25) NOT NULL,
    email VARCHAR(100),
    passport_data VARCHAR(100),
    budget_max DECIMAL(10, 2)
);

CREATE TABLE IF NOT EXISTS applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    property_id INTEGER,
    realtor_id INTEGER,
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    desired_district VARCHAR(100),
    status VARCHAR(30) NOT NULL DEFAULT 'Новая',
    comment TEXT,
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    FOREIGN KEY (property_id) REFERENCES properties(property_id)
);

CREATE TABLE IF NOT EXISTS contracts (
    contract_id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    realtor_id INTEGER NOT NULL,
    contract_num VARCHAR(50) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    monthly_rent DECIMAL(10, 2) NOT NULL,
    commission_fee DECIMAL(10, 2) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Действует',
    FOREIGN KEY (application_id) REFERENCES applications(application_id),
    FOREIGN KEY (property_id) REFERENCES properties(property_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);

INSERT OR IGNORE INTO districts (district_id, name, avg_price_sqm) VALUES
(1, 'Кировский район', 720.00),
(2, 'Советский район', 690.00),
(3, 'Октябрьский район', 660.00),
(4, 'Ленинский район', 640.00),
(5, 'Орджоникидзевский район', 540.00),
(6, 'Калининский район', 520.00),
(7, 'Дёмский район', 530.00);

INSERT OR IGNORE INTO realtors (realtor_id, full_name, role, phone, login, password_hash) VALUES
(1, 'Капустин Владислав', 'Администратор / Риелтор', '+7 (917) 345-12-89', 'kapustin', 'ufa2026');

INSERT OR IGNORE INTO owners (owner_id, full_name, phone, passport_data, egrn_number) VALUES
(1, 'Ибрагимов Руслан Тагирович', '+7 (917) 401-22-33', '80 15 456789', '02:55:010124:412'),
(2, 'Кузнецова Елена Викторовна', '+7 (927) 318-90-11', '80 18 112233', '02:55:020415:889');

INSERT OR IGNORE INTO properties (property_id, owner_id, district_id, property_type, address_ufa, rooms_count, area_total, floor_info, price_monthly, status, description) VALUES
(1, 1, 1, 'Квартира', 'г. Уфа, ул. Ленина, д. 42', 2, 58.5, '5/9', 38000, 'Активен', '2-к квартира в центре Уфы рядом с Гостиным двором.'),
(2, 2, 3, 'Квартира', 'г. Уфа, проспект Октября, д. 112', 1, 41.0, '8/16', 26000, 'Активен', '1-к квартира возле Горсовета.');
