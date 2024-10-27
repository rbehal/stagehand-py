async function processElements(chunk, scrollToChunk = true) {
  console.time("processElements:total");
  const viewportHeight = window.innerHeight;
  const chunkHeight = viewportHeight * chunk;

  // Calculate the maximum scrollable offset
  const maxScrollTop =
    document.documentElement.scrollHeight - window.innerHeight;

  // Adjust the offsetTop to not exceed the maximum scrollable offset
  const offsetTop = Math.min(chunkHeight, maxScrollTop);

  if (scrollToChunk) {
    console.time("processElements:scroll");
    await scrollToHeight(offsetTop);
    console.timeEnd("processElements:scroll");
  }

  const candidateElements = [];
  const DOMQueue = [...document.body.childNodes];
  const xpathCache = new Map();

  console.log("Stagehand (Browser Process): Generating candidate elements");
  console.time("processElements:findCandidates");

  while (DOMQueue.length > 0) {
    const element = DOMQueue.pop();

    let shouldAddElement = false;

    if (element && isElementNode(element)) {
      const childrenCount = element.childNodes.length;

      // Always traverse child nodes
      for (let i = childrenCount - 1; i >= 0; i--) {
        const child = element.childNodes[i];
        DOMQueue.push(child);
      }

      // Check if element is interactive
      if (isInteractiveElement(element)) {
        if (isActive(element) && isVisible(element)) {
          shouldAddElement = true;
        }
      }

      if (isLeafElement(element)) {
        if (isActive(element) && isVisible(element)) {
          shouldAddElement = true;
        }
      }
    }

    if (element && isTextNode(element) && isTextVisible(element)) {
      shouldAddElement = true;
    }

    if (shouldAddElement) {
      candidateElements.push(element);
    }
  }

  console.timeEnd("processElements:findCandidates");

  const selectorMap = {};
  let outputString = "";

  console.log(
    `Stagehand (Browser Process): Processing candidate elements: ${candidateElements.length}`
  );

  console.time("processElements:processCandidates");
  candidateElements.forEach((element, index) => {
    let xpath = xpathCache.get(element);
    if (!xpath) {
      xpath = generateXPath(element);
      xpathCache.set(element, xpath);
    }

    if (isTextNode(element)) {
      const textContent = element.textContent?.trim();
      if (textContent) {
        outputString += `${index}:${textContent}\n`;
      }
    } else if (isElementNode(element)) {
      const tagName = element.tagName.toLowerCase();
      const attributes = collectEssentialAttributes(element);

      const openingTag = `<${tagName}${attributes ? " " + attributes : ""}>`;
      const closingTag = `</${tagName}>`;
      const textContent = element.textContent?.trim() || "";

      outputString += `${index}:${openingTag}${textContent}${closingTag}\n`;
    }

    selectorMap[index] = xpath;
  });
  console.timeEnd("processElements:processCandidates");

  console.timeEnd("processElements:total");
  return {
    outputString,
    selectorMap,
  };
}

async function processDom(chunksSeen) {
  const { chunk, chunksArray } = await pickChunk(chunksSeen);
  const { outputString, selectorMap } = await processElements(chunk);

  console.log(
    `Stagehand (Browser Process): Extracted dom elements:\n${outputString}`
  );

  return {
    outputString,
    selectorMap,
    chunk,
    chunks: chunksArray,
  };
}

async function processAllOfDom() {
  console.log("Stagehand (Browser Process): Processing all of DOM");

  const viewportHeight = window.innerHeight;
  const documentHeight = document.documentElement.scrollHeight;
  const totalChunks = Math.ceil(documentHeight / viewportHeight);

  const chunkPromises = Array.from({ length: totalChunks }, (_, chunk) =>
    processElements(chunk, false)
  );

  const results = await Promise.all(chunkPromises);

  const concatenatedOutputString = results
    .map((result) => result.outputString)
    .join("");
  const allSelectorMap = results.reduce(
    (acc, result) => ({ ...acc, ...result.selectorMap }),
    {}
  );

  console.log(
    `Stagehand (Browser Process): All dom elements: ${concatenatedOutputString}`
  );

  return {
    outputString: concatenatedOutputString,
    selectorMap: allSelectorMap,
  };
}

async function scrollToHeight(height) {
  window.scrollTo({ top: height, left: 0, behavior: "smooth" });

  // Wait for scrolling to finish using the scrollend event
  await new Promise((resolve) => {
    let scrollEndTimer;
    const handleScrollEnd = () => {
      clearTimeout(scrollEndTimer);
      scrollEndTimer = window.setTimeout(() => {
        window.removeEventListener("scroll", handleScrollEnd);
        resolve();
      }, 200);
    };

    window.addEventListener("scroll", handleScrollEnd, { passive: true });
    handleScrollEnd();
  });
}

async function pickChunk(chunksSeen) {
  const viewportHeight = window.innerHeight;
  const documentHeight = document.documentElement.scrollHeight;

  const chunks = Math.ceil(documentHeight / viewportHeight);

  const chunksArray = Array.from({ length: chunks }, (_, i) => i);
  const chunksRemaining = chunksArray.filter((chunk) => {
    return !chunksSeen.includes(chunk);
  });

  const currentScrollPosition = window.scrollY;
  const closestChunk = chunksRemaining.reduce((closest, current) => {
    const currentChunkTop = viewportHeight * current;
    const closestChunkTop = viewportHeight * closest;
    return Math.abs(currentScrollPosition - currentChunkTop) <
      Math.abs(currentScrollPosition - closestChunkTop)
      ? current
      : closest;
  }, chunksRemaining[0]);
  const chunk = closestChunk;

  if (chunk === undefined) {
    throw new Error(`No chunks remaining to check: ${chunksRemaining}`);
  }
  return {
    chunk,
    chunksArray,
  };
}

const leafElementDenyList = ["SVG", "IFRAME", "SCRIPT", "STYLE", "LINK"];

const interactiveElementTypes = [
  "A",
  "BUTTON",
  "DETAILS",
  "EMBED",
  "INPUT",
  "LABEL",
  "MENU",
  "MENUITEM",
  "OBJECT",
  "SELECT",
  "TEXTAREA",
  "SUMMARY",
];

const interactiveRoles = [
  "button",
  "menu",
  "menuitem",
  "link",
  "checkbox",
  "radio",
  "slider",
  "tab",
  "tabpanel",
  "textbox",
  "combobox",
  "grid",
  "listbox",
  "option",
  "progressbar",
  "scrollbar",
  "searchbox",
  "switch",
  "tree",
  "treeitem",
  "spinbutton",
  "tooltip",
];

const interactiveAriaRoles = ["menu", "menuitem", "button"];

function isElementNode(node) {
  return node.nodeType === Node.ELEMENT_NODE;
}

function isTextNode(node) {
  const trimmedText = node.textContent?.trim().replace(/\s/g, "");
  return node.nodeType === Node.TEXT_NODE && trimmedText !== "";
}

function isVisible(element) {
  const rect = element.getBoundingClientRect();
  if (
    rect.width === 0 ||
    rect.height === 0 ||
    rect.top < 0 ||
    rect.top > window.innerHeight
  ) {
    return false;
  }
  if (!isTopElement(element, rect)) {
    return false;
  }

  const visible = element.checkVisibility({
    checkOpacity: true,
    checkVisibilityCSS: true,
  });

  return visible;
}

function isTextVisible(element) {
  const range = document.createRange();
  range.selectNodeContents(element);
  const rect = range.getBoundingClientRect();

  if (
    rect.width === 0 ||
    rect.height === 0 ||
    rect.top < 0 ||
    rect.top > window.innerHeight
  ) {
    return false;
  }
  const parent = element.parentElement;
  if (!parent) {
    return false;
  }
  if (!isTopElement(parent, rect)) {
    return false;
  }

  const visible = parent.checkVisibility({
    checkOpacity: true,
    checkVisibilityCSS: true,
  });

  return visible;
}

function isTopElement(elem, rect) {
  const points = [
    { x: rect.left + rect.width * 0.25, y: rect.top + rect.height * 0.25 },
    { x: rect.left + rect.width * 0.75, y: rect.top + rect.height * 0.25 },
    { x: rect.left + rect.width * 0.25, y: rect.top + rect.height * 0.75 },
    { x: rect.left + rect.width * 0.75, y: rect.top + rect.height * 0.75 },
    { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 },
  ];

  return points.some((point) => {
    const topEl = document.elementFromPoint(point.x, point.y);
    let current = topEl;
    while (current && current !== document.body) {
      if (current.isSameNode(elem)) {
        return true;
      }
      current = current.parentElement;
    }
    return false;
  });
}

function isActive(element) {
  if (
    element.hasAttribute("disabled") ||
    element.hasAttribute("hidden") ||
    element.getAttribute("aria-disabled") === "true"
  ) {
    return false;
  }

  return true;
}

function isInteractiveElement(element) {
  const elementType = element.tagName;
  const elementRole = element.getAttribute("role");
  const elementAriaRole = element.getAttribute("aria-role");

  return (
    (elementType && interactiveElementTypes.includes(elementType)) ||
    (elementRole && interactiveRoles.includes(elementRole)) ||
    (elementAriaRole && interactiveAriaRoles.includes(elementAriaRole))
  );
}

function isLeafElement(element) {
  if (element.textContent === "") {
    return false;
  }

  if (element.childNodes.length === 0) {
    return !leafElementDenyList.includes(element.tagName);
  }

  if (element.childNodes.length === 1 && isTextNode(element.childNodes[0])) {
    return true;
  }

  return false;
}

function generateXPath(element) {
  if (isElementNode(element) && element.id) {
    return `//*[@id='${element.id}']`;
  }

  const parts = [];
  while (element && (isTextNode(element) || isElementNode(element))) {
    let index = 0;
    let hasSameTypeSiblings = false;
    const siblings = element.parentElement
      ? Array.from(element.parentElement.childNodes)
      : [];

    for (let i = 0; i < siblings.length; i++) {
      const sibling = siblings[i];

      if (
        sibling.nodeType === element.nodeType &&
        sibling.nodeName === element.nodeName
      ) {
        index = index + 1;
        hasSameTypeSiblings = true;

        if (sibling.isSameNode(element)) {
          break;
        }
      }
    }

    if (element.nodeName !== "#text") {
      const tagName = element.nodeName.toLowerCase();
      const pathIndex = hasSameTypeSiblings ? `[${index}]` : "";
      parts.unshift(`${tagName}${pathIndex}`);
    }

    element = element.parentElement;
  }

  return parts.length ? `/${parts.join("/")}` : "";
}

function collectEssentialAttributes(element) {
  const essentialAttributes = [
    "id",
    "class",
    "href",
    "src",
    "aria-label",
    "aria-name",
    "aria-role",
    "aria-description",
    "aria-expanded",
    "aria-haspopup",
  ];

  const attrs = essentialAttributes
    .map((attr) => {
      const value = element.getAttribute(attr);
      return value ? `${attr}="${value}"` : "";
    })
    .filter((attr) => attr !== "");

  Array.from(element.attributes).forEach((attr) => {
    if (attr.name.startsWith("data-")) {
      attrs.push(`${attr.name}="${attr.value}"`);
    }
  });

  return attrs.join(" ");
}

window.processDom = processDom;
window.processAllOfDom = processAllOfDom;
window.processElements = processElements;
window.scrollToHeight = scrollToHeight;
