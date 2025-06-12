window.addEventListener('DOMContentLoaded', handleHashChange);
window.addEventListener('hashchange', handleHashChange);

function handleHashChange() {
  if (window.location.hash) {
    var anchor = window.location.hash.substring(1);
    var targetElement = document.getElementById(anchor);

    if (targetElement) {
      var elementsToChange = targetElement.getElementsByClassName('change-color');
      var trans = targetElement.getElementsByClassName('graft');

      if (trans.length > 0) {
        var computedStyle = getComputedStyle(trans[0]);
        var backgroundColor = computedStyle.backgroundColor;

        highlight(elementsToChange[0], backgroundColor);
      }
    }
  }
}


function highlight(obj, color) {
    let defaultBG = obj.style.backgroundColor;
    let defaultTransition = obj.style.transition;

    obj.style.transition = "background 1s";
    obj.style.backgroundColor = color;

    setTimeout(function()
    {
        obj.style.backgroundColor = defaultBG;
        setTimeout(function() {
            obj.style.transition = defaultTransition;
        }, 1000);
    }, 1000);
}