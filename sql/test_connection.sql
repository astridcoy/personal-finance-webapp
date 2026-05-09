SELECT TOP 10
    m.id_movimiento,
    m.fecha,
    c.nombre AS categoria,
    c.tipo,
    m.descripcion,
    m.monto
FROM dbo.movimientos m
INNER JOIN dbo.categorias c
    ON m.id_categoria = c.id_categoria
ORDER BY m.id_movimiento DESC;