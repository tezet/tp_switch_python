
var modal_wait_enable;
var modal_wait_disable;
var modal_input_name;

function wait_for_enable()
{
    $.ajax({ url: "edithandler?op=learn_on", success: function(data){
	  	modal_wait_enable.hide();
		modal_wait_disable.show();

		$('#on_input').attr('value', data);

		setTimeout(function(){
	  		wait_for_disable();
		}, 1000);
    }, dataType: "json" , });
}

function wait_for_disable(on_cmd)
{
    $.ajax({ url: "edithandler?op=learn_off&&on=on_cmd", success: function(data){
		modal_wait_disable.hide();
	  	modal_input_name.show();

		$('#off_input').attr('value', data);

    }, dataType: "json" , });
}

function cancel_learn()
{
    $.ajax({ url: "edithandler?op=learn_cancel", success: function(data){
    }, dataType: "json" , });
}

$(document).ready(function ()
{
	modal_wait_enable  = new $.UIkit.modal.Modal("#modal_wait_enable");
	modal_wait_disable = new $.UIkit.modal.Modal("#modal_wait_disable");
	modal_input_name   = new $.UIkit.modal.Modal("#modal_input_name");


	 $('#add_switch').click(function(){
		modal_wait_enable.show();
		wait_for_enable();
  	});

    $('.uk-modal-close').click(function(){
		cancel_learn();
  	});

  	$("#advanced_settings").hide();

  	$("#advanced_btn").click(function(){
  		$("#advanced_settings").toggle();
	});


});
