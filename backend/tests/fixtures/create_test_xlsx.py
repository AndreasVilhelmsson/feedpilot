import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["sku", "title", "description", 
           "category", "price", "color", "size", "brand"])
ws.append(["EXCEL-001", "Adidas Stan Smith", 
           "Klassisk sneaker i vitt läder med grön detalj",
           "Skor > Sneakers", "899.00", "vit", "42", "Adidas"])
ws.append(["EXCEL-002", "Nike Air Max 90",
           "Ikonisk löparsko med Air-dämpning och mesh-överdel",
           "Skor > Löparskor", "1299.00", "svart", "43", "Nike"])
ws.append(["EXCEL-003", "Fjällräven Kånken Mini",
           "Klassisk ryggsäck i Vinylon F, perfekt för vardagsbruk",
           "Väskor > Ryggsäckar", "699.00", "blå", "", "Fjällräven"])
wb.save("backend/tests/fixtures/test_feed.xlsx")
print("Klar!")