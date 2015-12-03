
function poll(){
    $.ajax({ url: "getstate", success: function(data){

		$.each(data, function (index, value) {
		        for( key in value )
		        {
		        	$('#switch' + key).toggles({on:value[key]});
		        }
		    });

    }, dataType: "json", complete: poll, timeout: 10000 });
}

function refresh_switches(){
    $.ajax({ url: "getstate", success: function(data){

		$.each(data, function (index, value) {
		        for( key in value )
		        {
		        	$('#switch' + key).toggles({on:value[key]});
		        }
		    });

    }, dataType: "json", timeout: 10000 });
}


function toggleSwitch(btnID, state)
{
	if (state)
		state = 1;
	else
		state = 0;

	$.post( "switch", { switch: btnID, state: state } );
}

$(document).ready(function ()
{

	poll();

	$('.toggle').toggles({
	    text: {
	      on: 'ON', // text for the ON position
	      off: 'OFF' // and off
	    },
	    on: false, // is the toggle ON on init
	    width: 100, // width used if not set in css
	    height: 40, // height if not set in css
	  });

	// Getting notified of changes, and the new state:
	$('.toggle').on('toggle', function (e, active) {
	    toggleSwitch($(this).attr('id'), active);
	});

	init_switches_state();

	$(window).on('focus', function() {
		refresh_switches();
	});

});