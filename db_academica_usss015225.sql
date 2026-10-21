-- Parcial II - USSS015225 - MySQL 8+
CREATE DATABASE IF NOT EXISTS db_academica CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE db_academica;

CREATE TABLE IF NOT EXISTS usuarios_usss015225 (
    idUsuario INT(10) NOT NULL AUTO_INCREMENT,
    usuario CHAR(35) NOT NULL,
    clave CHAR(35) NOT NULL,
    nombre CHAR(85) NOT NULL,
    `dirección` CHAR(100) NOT NULL,
    `teléfono` CHAR(9) NOT NULL,
    PRIMARY KEY (idUsuario),
    UNIQUE KEY uk_usuario (usuario)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- El primer usuario se crea con crear_usuario_inicial.py para almacenar
-- la contraseña de forma segura y permitir el primer inicio de sesión.
