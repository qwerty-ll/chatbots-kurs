px = int(input("X: "))
py = int(input("Y: "))
for y in range(3):
    row = ""
    for x in range(3):
        if x == px and y == py:
            row += "@ "
        else:
            row += "· "
    print(row.strip())
