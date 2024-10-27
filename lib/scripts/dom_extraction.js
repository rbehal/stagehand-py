window.getVisibleElements = () => {
  function isVisible(element) {
    const style = window.getComputedStyle(element);
    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      style.opacity !== "0"
    );
  }

  function isInteractive(element) {
    const interactiveTags = ["button", "a", "input", "select", "textarea"];
    return (
      interactiveTags.includes(element.tagName.toLowerCase()) ||
      element.hasAttribute("role")
    );
  }

  function generateXPath(element) {
    if (element.id) return `//*[@id="${element.id}"]`;
    if (!element.parentNode) return "";

    let siblings = element.parentNode.childNodes;
    let count = 1;
    for (let sibling of siblings) {
      if (sibling === element) break;
      if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
        count++;
      }
    }

    return (
      generateXPath(element.parentNode) +
      "/" +
      element.tagName.toLowerCase() +
      "[" +
      count +
      "]"
    );
  }

  const candidates = [];
  const walker = document.createTreeWalker(
    document.body,
    NodeFilter.SHOW_ELEMENT,
    null,
    false
  );

  let node;
  while ((node = walker.nextNode())) {
    if (!isVisible(node)) continue;

    if (node.children.length === 0 || isInteractive(node)) {
      const rect = node.getBoundingClientRect();
      candidates.push({
        xpath: generateXPath(node),
        text: node.textContent.trim(),
        tagName: node.tagName.toLowerCase(),
        isInteractive: isInteractive(node),
        attributes: Object.fromEntries(
          Array.from(node.attributes).map((attr) => [attr.name, attr.value])
        ),
        boundingBox: {
          x: rect.x,
          y: rect.y,
          width: rect.width,
          height: rect.height,
        },
      });
    }
  }
  return candidates;
};
