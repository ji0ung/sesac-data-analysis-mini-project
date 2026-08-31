from pbixray import PBIXRay

model = PBIXRay("model-check.pbix")
with open("pbix-inspect/model-report.txt", "w", encoding="utf-8") as output:
    output.write("TABLES\n")
    output.write(str(model.tables))
    output.write("\nSCHEMA\n")
    output.write(model.schema.to_string(index=False))
    output.write("\nRELATIONSHIPS\n")
    output.write(model.relationships.to_string(index=False))
