from wtforms import Form, StringField, RadioField, SelectField, TextAreaField, validators

class CreatePostForm(Form):
    post_title = StringField('Post title', [validators.Length(min=1,max=150),
                                            validators.DataRequired()], render_kw={"rows": 6, "placeholder": "Post title goes here..."})
    post_content = TextAreaField('Post content',
                                [validators.Length(min=1, max=10000), 
                                validators.DataRequired()], render_kw={"rows": 6, "placeholder": "Post content goes here..."})
    post_tags = StringField('Post Tags',
                            [validators.Length(min=1, max=1000), validators.Optional()], 
                            render_kw={"placeholder": "Separate tags with commas"})


