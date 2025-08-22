$(document).ready(function() {
    grecaptcha.ready(function() {
        $('form').submit(function(e){
            var form = this;
            e.preventDefault();
            grecaptcha.execute(recaptchaSiteKey, { action: 'submit' }).then(function(token) {
                $('#g-recaptcha-response').val(token);
                form.submit();
            });
        });
    });
});