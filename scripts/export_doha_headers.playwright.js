async () => {
  await page.addStyleTag({
    content: [
      "body { margin: 0 !important; background: #f4efe4 !important; }",
      "#export-stage { position: fixed; left: 0; top: 0; width: 1824px; height: 576px; overflow: hidden; z-index: 999999; background: #203b3f; }",
      "#export-stage .hero { width: 1824px !important; height: 576px !important; min-height: 0 !important; aspect-ratio: auto !important; padding: 0 !important; display: block !important; }",
      "#export-stage .hero::after { display: none !important; }",
      "#export-stage .content { display: none !important; }",
    ].join("\n"),
  });

  const exports = [
    ["mia-palms", "output/header-exports/mood-1.png"],
    ["west-bay-glass", "output/header-exports/mood-2.png"],
    ["mia-stone-water", "output/header-exports/mood-3.png"],
    ["al-wakrah-haze", "output/header-exports/mood-4.png"],
    ["hamad-port", "output/header-exports/mood-5.png"],
  ];

  const result = [];
  for (const [className, path] of exports) {
    await page.evaluate((selectedClass) => {
      document.getElementById("export-stage")?.remove();
      const original = document.querySelector(".hero." + selectedClass);
      const stage = document.createElement("div");
      stage.id = "export-stage";
      const clone = original.cloneNode(true);
      clone.querySelector(".content")?.remove();
      stage.appendChild(clone);
      document.body.appendChild(stage);
    }, className);
    await page.locator("#export-stage").screenshot({ path });
    result.push({ className, path });
  }
  return result;
}
