document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-toggle="collapse"]').forEach(item => {
        const collapseTarget = document.getElementById(item.getAttribute('data-target').replace('#', ''));

        updateMaxHeight(collapseTarget);

        item.addEventListener('click', function() {
            toggleCollapse(collapseTarget, this);
        });
    });

    document.querySelectorAll('.show-more-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            toggleShowMore(this);
        });
    });
});


$(document).ready(function() {
    var startY, endY;
    var threshold = 150;

    $('#filterBlockModalMobile').on('touchstart', function(event) {
        startY = event.originalEvent.touches[0].clientY;
        $(this).css('transition', 'none');
    });
    
    $('#filterBlockModalMobile').on('touchmove', function(event) {
        if (!event.cancelable) {
            return;
        }
        endY = event.originalEvent.touches[0].clientY;
        var distance = endY - startY;
        var modalHeight = $(this).outerHeight();
        var initialPixels = modalHeight * (25 / 100);
        var totalTranslate = initialPixels + distance;
        
        var scrollTop = $(this).find('.filter-mobile-modal-content').scrollTop();

        if (scrollTop === 0 && distance > 0) {
            event.preventDefault();
            $(this).css('transform', 'translateY(' + totalTranslate + 'px)');
        } else if (scrollTop != 0) {
            startY = event.originalEvent.touches[0].clientY;
        }
    });

    $('#filterBlockModalMobile').on('touchend', function(event) {
        var totalDistance = endY - startY;
        if (totalDistance > threshold) {
            closeModal();
        } else {
            openModal();
        }
    });
});

$(document).ready(function() {
    function moveBlock() {
        var windowWidth = $(window).width();
        if (windowWidth < 768) {
            $('#filterBlockMovement').appendTo('#filterMobileModalContent');
            $('#filterBlockMovement').css('visibility', 'visible');
            $('.filter-mobile-modal-open').show();
        } else {
            $('#filterBlockMovement').appendTo('#filterBlockDesktop');
            $('#filterBlockMovement').css('visibility', 'visible');
            $('.filter-mobile-modal-open').hide();
        }
    }
    moveBlock();
    $(window).resize(moveBlock);

});



document.addEventListener('DOMContentLoaded', function() {
    const sortSelect = document.querySelector('.sort-select');
    const trigger = sortSelect.querySelector('.sort-select__trigger');
    const optionsContainer = sortSelect.querySelector('.sort-options');
    const arrow = trigger.querySelector('.product-sort-arrow');

    trigger.addEventListener('click', function() {
        sortSelect.classList.toggle('open');
        arrow.style.transform = sortSelect.classList.contains('open') ? 'rotate(180deg)' : 'rotate(0deg)';
    });

    optionsContainer.querySelectorAll('.sort-option').forEach(option => {
        option.addEventListener('click', function() {
            trigger.querySelector('span').textContent = this.textContent;

            optionsContainer.querySelector('.sort-option.selected').classList.remove('selected');
            this.classList.add('selected');

            sortSelect.classList.remove('open');
            arrow.style.transform = 'rotate(0deg)';
        });
    });

    document.addEventListener('click', function(e) {
        if (!sortSelect.contains(e.target) && !optionsContainer.contains(e.target)) {
            sortSelect.classList.remove('open');
            arrow.style.transform = 'rotate(0deg)';
        }
    }, true);
});




function toggleCollapse(collapseTarget, toggleButton) {
    const isOpen = collapseTarget.style.getPropertyValue('--max-height') !== '0px';

    if (isOpen) {
        collapseTarget.style.setProperty('--max-height', '0px');
        toggleButton.querySelector('img').style.transform = 'rotate(0deg)';
    } else {
        updateMaxHeight(collapseTarget);
        collapseTarget.style.setProperty('--max-height', `${collapseTarget.scrollHeight}px`);
        toggleButton.querySelector('img').style.transform = 'rotate(180deg)';
    }
}

function toggleShowMore(button) {
    const showMore = button.getAttribute('data-show') === 'true';
    const targetClass = button.getAttribute('data-target');

    const collapseTarget = button.closest('.collapse');
    const extraItems = collapseTarget.querySelectorAll('.' + targetClass);
    extraItems.forEach(item => {
        item.style.display = showMore ? 'none' : 'block';
    });

    button.setAttribute('data-show', showMore ? 'false' : 'true');
    button.textContent = showMore ? 'Показать все' : 'Скрыть';

    if (collapseTarget) {
        updateMaxHeight(collapseTarget, showMore);
    }
}

function updateMaxHeight(collapseElement, collapsing) {
    let totalHeight = 0;
    if (collapsing) {
        const visibleItems = collapseElement.querySelectorAll(':scope > *:not(.hide)');
        visibleItems.forEach(item => {
            if (item.style.display !== 'none') {
                const style = window.getComputedStyle(item);

                const height = item.offsetHeight;
                const marginTop = parseInt(style.marginTop);
                const marginBottom = parseInt(style.marginBottom);
                totalHeight += height + (isNaN(marginTop) ? 0 : marginTop) + (isNaN(marginBottom) ? 0 : marginBottom);
            }
        });
    } else {
        totalHeight = collapseElement.scrollHeight;
    }
    collapseElement.style.setProperty('--max-height', `${totalHeight}px`);
}


function openModal() {
    $('body').css('overflow', 'hidden');
    $('#filterBlockModalMobile' ).css({
        'transform': 'translateY(25%)',
        'transition': 'transform 0.5s ease-in-out'
    });
}

function closeModal() {
    $('body').css('overflow', '');
    $('#filterBlockModalMobile').css({
        'transform': 'translateY(125%)',
        'transition': 'transform 0.5s ease-in-out'
    });
}