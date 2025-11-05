(function($) {
    'use strict';

    /**
     * Clear opposite field based on point_type selection
     * Both fields remain visible, but only one can be selected at a time
     */
    function togglePointFields(row) {
        var pointTypeSelect = row.find('select[id$="-point_type"]');
        var busStopSelect = row.find('select[id$="-bus_stop"]');
        var waypointSelect = row.find('select[id$="-waypoint"]');

        if (!pointTypeSelect.length) return;

        var selectedType = pointTypeSelect.val();

        if (selectedType === 'bus_stop') {
            // Clear waypoint selection when bus_stop is selected
            waypointSelect.val('');
        } else if (selectedType === 'waypoint') {
            // Clear bus_stop selection when waypoint is selected
            busStopSelect.val('');
        } else {
            // Default: clear waypoint (bus_stop is the usual thing)
            waypointSelect.val('');
        }
    }

    /**
     * Update sequence numbers based on row order
     */
    function updateSequenceNumbers() {
        var sequence = 1;
        // Try multiple selectors to find the inline rows
        var rows = $('#route_waypoint_set-group tbody tr, .inline-related tbody tr, [id*="route_waypoint"] tbody tr');

        rows.each(function() {
            var row = $(this);
            if (!row.hasClass('empty-form') && row.is(':visible')) {
                var deleteCheckbox = row.find('input[id$="-DELETE"]');
                // Skip rows marked for deletion
                if (!deleteCheckbox.is(':checked')) {
                    var sequenceInput = row.find('input[id$="-sequence"]');
                    if (sequenceInput.length) {
                        sequenceInput.val(sequence);
                        sequence++;
                    }
                }
            }
        });
    }

    /**
     * Initialize toggle for all existing rows
     */
    function initializeToggles() {
        var rows = $('#route_waypoint_set-group tbody tr, .inline-related tbody tr, [id*="route_waypoint"] tbody tr');
        rows.each(function() {
            var row = $(this);
            if (!row.hasClass('empty-form')) {
                togglePointFields(row);
            }
        });
        // Update sequence numbers on load
        setTimeout(updateSequenceNumbers, 100);
    }

    /**
     * Bind change event to point_type selects
     */
    function bindToggleEvents() {
        $(document).on('change', 'select[id$="-point_type"]', function() {
            var row = $(this).closest('tr');
            togglePointFields(row);
        });

        // Prevent selecting both bus stop and waypoint
        $(document).on('change', 'select[id$="-bus_stop"]', function() {
            if ($(this).val()) {
                var row = $(this).closest('tr');
                var pointTypeSelect = row.find('select[id$="-point_type"]');
                pointTypeSelect.val('bus_stop');
                row.find('select[id$="-waypoint"]').val('');
            }
        });

        $(document).on('change', 'select[id$="-waypoint"]', function() {
            if ($(this).val()) {
                var row = $(this).closest('tr');
                var pointTypeSelect = row.find('select[id$="-point_type"]');
                pointTypeSelect.val('waypoint');
                row.find('select[id$="-bus_stop"]').val('');
            }
        });
    }

    /**
     * Set default to bus_stop for new rows
     */
    function setDefaultForNewRows() {
        $(document).on('formset:added', function(event, $row) {
            // Set default to bus_stop
            var pointTypeSelect = $row.find('select[id$="-point_type"]');
            if (pointTypeSelect.length && !pointTypeSelect.val()) {
                pointTypeSelect.val('bus_stop');
            }
            togglePointFields($row);
            // Update sequence numbers after adding a row (with slight delay)
            setTimeout(updateSequenceNumbers, 50);
        });

        // Update sequence when delete checkbox is clicked
        $(document).on('change', 'input[id$="-DELETE"]', function() {
            setTimeout(updateSequenceNumbers, 50);
        });

        // Update sequence when any field changes (for immediate feedback)
        $(document).on('change', 'select[id$="-bus_stop"], select[id$="-waypoint"]', function() {
            setTimeout(updateSequenceNumbers, 50);
        });
    }

    // Initialize on document ready
    $(document).ready(function() {
        initializeToggles();
        bindToggleEvents();
        setDefaultForNewRows();
    });

    // Re-initialize when inline formsets are added (Django admin dynamic forms)
    if (typeof django !== 'undefined' && django.jQuery) {
        django.jQuery(document).on('formset:added', function(event, $row, formsetName) {
            if (formsetName === 'route_waypoints') {
                // Set default to bus_stop for new rows
                var pointTypeSelect = $row.find('select[id$="-point_type"]');
                if (pointTypeSelect.length) {
                    pointTypeSelect.val('bus_stop');
                }
                togglePointFields($row);
                // Update sequence numbers after adding
                updateSequenceNumbers();
            }
        });
    }

})(django.jQuery || jQuery);
