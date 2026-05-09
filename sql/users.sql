CREATE TABLE usuarios (
    id_usuario    INT IDENTITY(1,1) PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    creado_en     DATETIME     DEFAULT GETDATE()
);